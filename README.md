#Hargassener python telent
ce script tourne sur un Rasberry pi.
Il ecoute une chaudiere a granulés Hargassner NanoPK sur son port telnet
et ecrit les valeurs dans une BDD MySQL ou MariaDB 

-----------------------------------------------------------------------------------------------------

this script is running on raspberry pi
it listen an Hargassner NanoPK Boiler on telnet
and then it write data in MySQL or MariaDB on localhost or anoter server

Module to install for mariadb

```
pip3 install mariadb
pip3 install schedule
pip3 install telnetlib3
```

For VictoriaMetrics
```
pip3 install prometheus-push-client
```

I use grafana to visualize data

Plan:
 - use victoria metric
 - use docker compose
