#!/usr/bin/python
# -*- coding: utf-8 -*-

# auteur : niclange
# version 1.3
# python version 3.x

# ce script tourne sur un Rasberry pi
# il ecoute une chaudiere a granulés Hargassner NanoPK sur son port telnet
# et il ecrit les valeurs dans une BDD MySQL ou MariaDB sur un NAS Synology
# fonctionne avec les chaudieres data, classic and HSV  equipées de touchtronic 
# la requete pour créer les tables sont disponibles dans les fichiers create_table_data.sql et create_table_consommation.sql
# prérequis : MysQLdb doit etre installé sur la machine
# optionnel : SQlite3 doit etre installé sur la machine pour activer le mode backup qui copie en local en cas d'indispo de MySQL

# this script is running on raspberry pi
# it listen an Hargassner NanoPK Boiler on telnet
# and then it write data in MySQL or MariaDB on a NAS Synology
# work with data, classic and HSV boiler equiped with touchtronic + internet gateway
# may work without gateway (to be tested)
# to create the database, use the query in createBDD.sql

# Import socket module
import telnetlib               
import time
from datetime import date,timedelta
import mariadb   # MySQLdb must be installed by yourself
import sys
import logging
import schedule
import os


#----------------------------------------------------------#
#        parametres                                        #
#----------------------------------------------------------#
DB_SERVER = 'localhost'   # MySQL : IP server (localhost si mySQL est sur la meme machine)
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

DB_SERVER = os.getenv('DB_SERVER_HOST',DB_SERVER)
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
        break
    except:
        logger.critical("Connexion a la chaudiere impossible")
        sys.exit("Erreur connexion chaudiere")
        
try:
    db = mariadb.connect(host=DB_SERVER, 
                         user=DB_USER,  
                         password=DB_PWD, 
                         port=3306, 
                         database=DB_BASE)
    db.autocommit = True
    db.auto_reconnect = True
    
except mariadb.Error as e:
        logger.error("MariaDB is down : %s", e)
        print(f"Error connecting to MariaDB Platform: {e}")
        sys.exit(1)   
  



#----------------------------------------------------------#
#             declaration threads                          #
#----------------------------------------------------------#

#################################################################
# toutes les 2h ce thread verifie si on change de journée
# et calcul la conso de la veille avant de l'ecrire dans la table consommation
def thread_consommation():
    while True:
        try:
            cursor = db.cursor()
            cursor.execute("""SELECT dateB FROM consommation
                            ORDER by dateB DESC LIMIT 1 """)
            result = cursor.fetchone ()
            last_conso = result[0] + timedelta(days=1)
           
            if date.today() > last_conso:
                cursor.execute("""SELECT DATE(dateB),MAX(c99)-MIN(c99),FORMAT(AVG(c6), 1) FROM data
                                GROUP BY DATE(dateB)
                                ORDER by dateB DESC LIMIT 1,1 """)
                result = cursor.fetchone ()
                cursor.execute("""INSERT INTO consommation (dateB, conso, Tmoy) VALUES ('%s','%s','%s')""" % (result[0],result[1],result[2]))
            db.commit()
            db.close()
        except:
            logger.error('Erreur dans le Thread consommation')
        time.sleep(7200)


#thread2 = Thread(target=thread_consommation)
#thread2.start()
#time.sleep(5) #laisse le temps au buffer de se remplir
    
#----------------------------------------------------------#
#             suite du programme                           #
#----------------------------------------------------------#

#------preparation requete----------
list_champ = ", ?" * nbre_param
requete = "INSERT INTO data  VALUES (null" + list_champ + ")" # null correspond au champ id
 
def registerData():
    tn = telnetlib.Telnet(host=IP_CHAUDIERE)
    message = tn.read_until(b"\n", timeout=2).decode("ascii")
    tn.close()
    if message[0:2] == "pm":
        datebuff = time.strftime('%Y-%m-%d %H:%M:%S') #formating date for mySQL
        buff_liste=message.split()    # transforme la string du buffer en liste 
        logger.debug(buff_liste)
        print(f"nombre d'élément de la liste : {len(buff_liste)}")
        buff_liste[0] = datebuff       # remplace la valeur "pm" par la date
        list_liste = buff_liste [0:nbre_param]# selectionne les valeurs voulues, la valeur (nbre_param)doit correspondre au nombre de %s ci dessous
        tupl_liste = tuple(list_liste) # transforme la liste en tuple (necessaire pour le INSERT)
        try:    
            cursor = db.cursor()
            cursor.execute(requete, tupl_liste)
            cursor.close()
        except mariadb.Error as e:
            logger.error(f'insert KO {e}')
            print(f'insert KO {e}')
    else:
        logger.warning(message)


    

schedule.every(FREQUENCY).seconds.do(registerData)
while 1:
    schedule.run_pending()
    time.sleep(1)
        
