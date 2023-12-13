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
from hargdata import Heater
from hargdata import Temperatures
from hargdata import Boiler
from datetime import datetime
import sys
import logging
import schedule
import os
import paho.mqtt.publish as publish
from dataclasses import dataclass
from dataclasses_json import dataclass_json
#----------------------------------------------------------#
#        parametres                                        #
#----------------------------------------------------------#
mqtt_broker_host  = '192.168.1.166'   
mqtt_topic_tmp = 'home/livingroom/temperature'       
mqtt_topic_boiler = 'home/hargassner/boiler'
mqtt_topic_heater = 'home/hargassner/heater'
mqtt_username = 'home'        
mqtt_password  = 'myhome56'          
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

handler_debug = logging.basicConfig(level=logging.INFO)
logger.addHandler(handler_debug)

#----------------------------------------------------------#
#      init environment variable                           #
#----------------------------------------------------------#

#DB_SERVER = os.getenv('DB_SERVER_HOST',DB_SERVER)
IP_CHAUDIERE = os.getenv('IP_CHAUD',IP_CHAUDIERE)
mqtt_username = os.getenv('DB_USER',mqtt_username)
mqtt_password = os.getenv('DB_PWD',mqtt_password)
FIRMWARE_CHAUD = os.getenv('FIRMWARE_CHAUD',FIRMWARE_CHAUD)
mqtt_broker_host = os.getenv('IP_MQTT',mqtt_broker_host)
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
        break
    except:
        logger.critical("Connexion a la chaudiere impossible")
        sys.exit("Erreur connexion chaudiere")



  

auth = {'username': mqtt_username, 'password': mqtt_password}
 
def registerData():
    tn = telnetlib.Telnet(host=IP_CHAUDIERE)
    message = tn.read_until(b"\n", timeout=2).decode("ascii")
    tn.close()
    if message[0:2] == "pm":
        buff_liste=message.split()    # transforme la string du buffer en liste 
        logger.debug(buff_liste)
        print(f"nombre d'élément de la liste : {len(buff_liste)}")
        n = -1
        messages = []
        boiler = Boiler()
        temps = Temperatures()
        heater = Heater()
        for data in buff_liste:
            metric_name = "c" + str(n)
            labels = {"item": "NanoPK"}
            if n == 0 :
                metric_name = "status"
                heater.status = data
            elif n == 3:
                metric_name = "tmp_chaudiere"
                heater.tmp_chaudiere = data
            elif n == 5:
                metric_name = "tmp_fumee"
                heater.tmp_fumee = data
            elif n == 23:     
                metric_name = "reel_retour"
                heater.reel_retour = data
            elif n == 24:     
                metric_name = "cons_retour"
                heater.cons_retour = data
            elif n == 15:     
                metric_name = "tmp_ext"
                temps.tmp_ext = data
            elif n == 16:     
                metric_name = "tmp_ext_moyen"
                heater.tmp_ext_moyen = data
            elif n == 8:
                metric_name = "puissance"
                heater.puissance = data
            elif n == 32:
                metric_name = "minutes_fonct_vis" 
                heater.minutes_fonct_vis = data
            elif n == 33:        
                metric_name = "tps_marche_ve"
                heater.tps_marche_ve = data
            elif n == 35:        
                metric_name = "nb_mvt_grille" 
                heater.nb_mvt_grille = data
            elif n == 56:        
                metric_name = "tmp_reel_depart"
                heater.tmp_reel_depart = data
            elif n == 58:        
                metric_name = "tmp_ambiante"
                temps.tmp_ambiante = data 
            elif n == 95:
                metric_name = "tmp_eau_ballon"
                boiler.tmp_eau_ballon = data
            n = n + 1
        
        msg = {
            'topic': mqtt_topic_tmp, 
            'payload': temps.to_json(),
            'retain': True
        }
        messages.append(msg)
        msg = {
            'topic': mqtt_topic_boiler, 
            'payload': boiler.to_json(),
            'retain': True
        }
        messages.append(msg)
        msg = {
            'topic': mqtt_topic_heater, 
            'payload':heater.to_json(),
            'retain': True
        }
        messages.append(msg)
        publish.multiple(msgs=messages, hostname=mqtt_broker_host, auth=auth)
           
        
    else:
        logger.warning(message)


    

schedule.every(FREQUENCY).seconds.do(registerData)
while 1:
    schedule.run_pending()
    time.sleep(1)
        
