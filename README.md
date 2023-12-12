#Hargassener python telent
ce script tourne sur un Rasberry pi.
Il ecoute une chaudiere a granulés Hargassner NanoPK sur son port telnet
et ecrit les valeurs dans une BDD MySQL ou MariaDB 

On peut trouve l'image pour faire la passerelle avec mqtt : niclange/hargassnermqtt
-----------------------------------------------------------------------------------------------------

this script is running on raspberry pi
it listen an Hargassner NanoPK Boiler on telnet
and then it write data in MySQL or MariaDB on localhost or anoter server

Module core
```
pip3 install schedule
pip3 install telnetlib3
```

Module to install for mariadb

```
pip3 install mariadb
```

For Mqtt (Home Assistant)

```
pip3 install paho-mqtt
pip3 install dataclasses-json
```

I use grafana to visualize data

Plan:
 - use victoria metric
 - use docker compose


docker build -t niclange/hargassnermqtt:v1