#! /usr/bin/python
# -*- coding: UTF-8 -*-
import sys, os, os.path, logging
import Thawab.core
from Thawab.webApp import webApp

prefix=os.path.dirname(sys.argv[0])
th=Thawab.core.ThawabMan()

myLogger=logging.getLogger('ThawabWebAppTest')
h=logging.StreamHandler() # in production use WatchedFileHandler or RotatingFileHandler
h.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
myLogger.addHandler(h)
myLogger.setLevel(logging.INFO)

from paste import httpserver
app=webApp(
  th,True, 
  os.path.join(prefix,'thawab-files','templates'),
  staticBaseDir={'/_files/':os.path.join(prefix,'thawab-files','media')},
  logger=myLogger
  );
# for options see http://pythonpaste.org/modules/httpserver.html
httpserver.serve(app, host='0.0.0.0', port='8080') # to serve publically
#httpserver.serve(app, host='127.0.0.1', port='8080') # to serve localhost

