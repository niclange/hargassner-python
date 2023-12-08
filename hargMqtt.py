#!/usr/bin/python
# -*- coding: utf-8 -*-

# auteur : niclange
# version 1.0
# python version 3.x

# ce script tourne sur un Rasberry pi
# il ecoute une chaudiere a granulés Hargassner NanoPK sur son port telnet
# et il ecrit les valeurs dans une BDD MySQL ou MariaDB sur un NAS Synology
# fonctionne avec les chaudieres data, classic and HSV  equipées de touchtronic 
# la requete pour créer les tables sont disponibles dans les fichiers create_table_data.sql et create_table_consommation.sql
# prérequis : Victoria Metrics doit être accéssible


# this script is running on raspberry pi
# it listen an Hargassner NanoPK Boiler on telnet
# and then it write data in MySQL or MariaDB on a NAS Synology
# work with data, classic and HSV boiler equiped with touchtronic + internet gateway
# may work without gateway (to be tested)
# to create the database, use the query in createBDD.sql

# Import socket module
import telnetlib               
import time

from datetime import datetime
import sys
import logging
import schedule
import os
import prometheus_push_client as ppc

#----------------------------------------------------------#
#        parametres                                        #
#----------------------------------------------------------#
DB_SERVER = 'victoria'   # MySQL : IP server (localhost si mySQL est sur la meme machine)
DB_BASE = 'Hargassner'        # MySQL : database name
DB_USER = 'root'        # MySQL : user  
DB_PWD = ''           # MySQL : password 
IP_CHAUDIERE = '192.168.1.84'
FIRMWARE_CHAUD = 'x'        # firmware de la chaudiere

MODE_BACKUP = False          # True si SQlite3 est installé , sinon False  
FREQUENCY = 30              # Periodicité (reduit le volume de data mais reduit la précision)
                            # (1 = toutes)     1 mesure chaque seconde
                            # (5)              1 mesure toutes les 5 secondes
                            # ...
                            # une valeur trop faible entraine de gros volume en BDD et surtout des grosses 
                            # lenteurs pour afficher les graphiques : defaut 60sec , evitez de descendre sous les 10 sec
  
backup_row = 0
backup_mode = 0

if FIRMWARE_CHAUD == '14d':
    nbre_param = 174
elif FIRMWARE_CHAUD == '14e':
    nbre_param = 174
elif FIRMWARE_CHAUD == '14f':
    nbre_param = 174
elif FIRMWARE_CHAUD == '14g':
    nbre_param = 190
else:
    nbre_param = 153
   
#----------------------------------------------------------#
#        definition des logs                               #
#----------------------------------------------------------#
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('log')
logger.setLevel(logging.DEBUG) # choisir le niveau de log : DEBUG, INFO, ERROR...

handler_debug = logging.FileHandler("trace.log", mode="a", encoding="utf-8")
handler_debug.setFormatter(formatter)
handler_debug.setLevel(logging.DEBUG)
logger.addHandler(handler_debug)

#----------------------------------------------------------#
#      init environment variable                           #
#----------------------------------------------------------#

#DB_SERVER = os.getenv('DB_SERVER_HOST',DB_SERVER)
IP_CHAUDIERE = os.getenv('IP_CHAUD',IP_CHAUDIERE)
DB_USER = os.getenv('DB_USER',DB_USER)
DB_PWD = os.getenv('DB_PWD',DB_PWD)
FIRMWARE_CHAUD = os.getenv('FIRMWARE_CHAUD',FIRMWARE_CHAUD)

#----------------------------------------------------------#
#       check telnet for Connection to Hargassner          #
#----------------------------------------------------------#
i=0 
while True:
    try:
        tn = telnetlib.Telnet(host=IP_CHAUDIERE)
        data = tn.read_until(b"\n", timeout=2).decode("ascii")
        print(data)
        tn.close()
        pusher = Pusher("http://localhost:8428/api/v1/write")
        break
    except:
        logger.critical("Connexion a la chaudiere impossible")
        sys.exit("Erreur connexion chaudiere")
     
  

#------preparation requete----------
list_champ = ", ?" * nbre_param
requete = "INSERT INTO data  VALUES (null" + list_champ + ")" # null correspond au champ id
 
def registerData():
    metrics = []
    tn = telnetlib.Telnet(host=IP_CHAUDIERE)
    message = tn.read_until(b"\n", timeout=2).decode("ascii")
    tn.close()
    if message[0:2] == "pm":
        timestamp=int(datetime.now().timestamp())
        buff_liste=message.split()    # transforme la string du buffer en liste 
        logger.debug(buff_liste)
        print(f"nombre d'élément de la liste : {len(buff_liste)}")
        n = 0
        for data in buff_liste:
            metric_name = "c"+n
            labels = {"item": "NanoPK"}
            if n == 0 :
                metric_name = "status"
            elif n == 3:
                metric_name = "tmp_chaudiere"
            elif n == 5:
                 metric_name = "tmp_fumee"
            elif n == 23:     
                metric_name = "reel_retour"
            elif n == 24:     
                metric_name = "cons_retour"
            elif n == 15:     
                metric_name = "tmp_ext"
            elif n == 16:     
                metric_name = "tmp_ext_moyen"
            elif n == 8:
                metric_name = "puissance"
            elif n == 32:
                metric_name = "minutes_fonct_vis" 
            elif n == 33:        
                metric_name = "tps_marche_ve" 
            elif n == 35:        
                metric_name = "nb_mvt_grille" 
            elif n == 56:        
                metric_name = "tmp_reel_depart" 
            elif n == 58:        
                metric_name = "tmp_ambiante" 
            elif n == 95:
                metric_name = "tmp_eau_ballon"
            
            metric = Metric(metric_name, labels)
            metric.add_sample("nanopk", data , timestamp=int(datetime.now().timestamp()))
            pusher.push(metric)
            n = n+1
        
    else:
        logger.warning(message)


    

schedule.every(FREQUENCY).seconds.do(registerData)
while 1:
    schedule.run_pending()
    time.sleep(1)
        
