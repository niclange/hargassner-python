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
from datetime import date,datetime,timedelta
import mariadb   # MySQLdb must be installed by yourself
import sys
import os.path
import logging
from threading import Thread

#----------------------------------------------------------#
#        parametres                                        #
#----------------------------------------------------------#
DB_SERVER = 'localhost'   # MySQL : IP server (localhost si mySQL est sur la meme machine)
DB_BASE = 'Hargassner'        # MySQL : database name
DB_USER = 'hargassner'        # MySQL : user  
DB_PWD = 'password'           # MySQL : password 
IP_CHAUDIERE = '192.168.1.84'
FIRMWARE_CHAUD = 'x'        # firmware de la chaudiere
PATH_HARG = "/home/nlange/hargassner/" #chemin ou se trouve ce script

MODE_BACKUP = False          # True si SQlite3 est installé , sinon False  
INSERT_GROUPED = 1          # regroupe n reception avant d'ecrire en base :INSERT_GROUPED x FREQUENCY = temps en sec
FREQUENCY = 60              # Periodicité (reduit le volume de data mais reduit la précision)
                            # (1 = toutes)     1 mesure chaque seconde
                            # (5)              1 mesure toutes les 5 secondes
                            # ...
                            # une valeur trop faible entraine de gros volume en BDD et surtout des grosses 
                            # lenteurs pour afficher les graphiques : defaut 60sec , evitez de descendre sous les 10 sec
# ne pas modifier ci dessous
MSGBUFSIZE=600
PORT = 23    
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
    nbre_param = 151
   
#----------------------------------------------------------#
#        definition des logs                               #
#----------------------------------------------------------#
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('log')
logger.setLevel(logging.INFO) # choisir le niveau de log : DEBUG, INFO, ERROR...

handler_debug = logging.FileHandler(PATH_HARG + "trace.log", mode="a", encoding="utf-8")
handler_debug.setFormatter(formatter)
handler_debug.setLevel(logging.DEBUG)
logger.addHandler(handler_debug)

#----------------------------------------------------------#
#        socket for Connection to Hargassner               #
#----------------------------------------------------------#
while True:
    try:
        tn = telnetlib.Telnet(IP_CHAUDIERE)
        print(tn.read_all().decode("ascii"))
        break
    except:
        logger.critical("Connexion a la chaudiere impossible")
        time.sleep(5)
        
try:
    db = mariadb.connect(host=DB_SERVER, 
                         user=DB_USER,  
                         password=DB_PWD, 
                         port=3306, 
                         database=DB_BASE)
    cursor = db.cursor()
except mariadb.Error as e:
        logger.error("MariaDB is down : %s", e)
        print(f"Error connecting to MariaDB Platform: {e}")
        sys.exit(1)   
  
def query_db(sql):
    try: 
        cursor.execute(sql)
        logger.debug("Ecriture en bdd OK")
    except mariadb.Error as e: 
        print(f"Error: {e}")    
   
#----------------------------------------------------------#
#             initialisation table consommation            #
#             au 1er lancement du script
#             si la table est vide on rempli une ligne a vide
#----------------------------------------------------------#
try:
    cursor.execute("""SELECT COUNT(dateB) FROM consommation """)
    compt = cursor.fetchone ()
    if compt[0] == 0:
        dateH =  date.today() + timedelta(days=-1)
        cursor.execute("INSERT INTO consommation (dateB, conso, Tmoy) VALUES (?,?,?)", (dateH,0,0))
except:
    logger.error('Erreur initialisation table consommation')

#----------------------------------------------------------#
#             declaration threads                          #
#----------------------------------------------------------#

#################################################################
# toutes les 2h ce thread verifie si on change de journée
# et calcul la conso de la veille avant de l'ecrire dans la table consommation
def thread_consommation():
    while True:
        try:
            db = MySQLdb.connect(DB_SERVER, DB_USER, DB_PWD, DB_BASE)
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


#################################################################
# ce thread ecoute la chaudiere qui emet toute les 1 seconde
# la suite du programme vient piocher la valeur du buffer quand elle en a besoin (60sec par defaut).
# cette methode est plus efficace que d'ecouter la chaudiere uniquement quand on a besoin
# car on tombe sur des buffer en cours d'emission(incomplet) ce qui genere beaucoup d'erreur
def thread_buffer():
    global bufferOK
    while True:
        try:
            buffer = s.recv(MSGBUFSIZE) # waiting a packet (waiting as long as s.recv is empty)
            if buffer[0:2] == "pm":
                bufferOK = buffer
            else:
                logger.debug('buffer ERREUR pm')
        except:
            logger.error('buffer ERREUR lecture')
        # except KeyboardInterrupt:
            # thread1._Thread__stop()
            # break

## execution thread parallele#############################################

thread1 = Thread(target=thread_buffer)
thread2 = Thread(target=thread_consommation)
thread1.start()
thread2.start()
time.sleep(5) #laisse le temps au buffer de se remplir
    
#----------------------------------------------------------#
#             suite du programme                           #
#----------------------------------------------------------#
    
i=0
tableau = []
#------preparation requete----------
list_champ = ",'%s'" * nbre_param
requete = "INSERT INTO data  VALUES (null" + list_champ + ")" # null correspond au champ id
 
while True:
    try:
        if bufferOK[0:2] == "pm":
            datebuff = time.strftime('%Y-%m-%d %H:%M:%S') #formating date for mySQL
            buff_liste=bufferOK.split()    # transforme la string du buffer en liste 
            logger.debug(buff_liste)
            buff_liste[0] = datebuff       # remplace la valeur "pm" par la date
            list_liste = buff_liste [0:nbre_param]# selectionne les valeurs voulues, la valeur (nbre_param)doit correspondre au nombre de %s ci dessous
            tupl_liste = tuple(list_liste) # transforme la liste en tuple (necessaire pour le INSERT)
            tableau.append(tupl_liste)     # cumule les tuples dans un tableau
            i = i + 1
            try:
                if i == INSERT_GROUPED:
                    tableau = tuple(tableau)  # crée un tuple de tuple
                    for x in range(INSERT_GROUPED):
                        query_db( requete % tableau[x] ) 
                    
                    logger.debug('write DB : %s', tableau[0][0])
                    i = 0
                    tableau = []
                time.sleep(FREQUENCY - 1)
            except:
                logger.error('insert KO')
        else:
            logger.debug(bufferOK)

    except :
        logger.error('le if pm est KO, buffer non defini')
        time.sleep(1)
        continue

        
def fermeture(signal,frame):
    # arret du script 
    thread1._Thread__stop()
    thread2._Thread__stop()
    s.close()   

# interception du signal d'arret du service   pour fermer les threads  
signal.signal(signal.SIGTERM, fermeture) 
        
