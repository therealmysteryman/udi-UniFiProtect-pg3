#!/usr/bin/env python3

"""
This is a NodeServer for Unifi Protect written by automationgeek (Jean-Francois Tremblay)
based on the NodeServer template for Polyglot v2 written in Python2/3 by Einstein.42 (James Milne) milne.james@gmail.com
"""
import udi_interface
import warnings 
import hashlib
import aiohttp
import asyncio
import time
import json
import sys

from copy import deepcopy
from urllib.parse import quote
from aiohttp import ClientSession, CookieJar
from pyunifiprotect.unifi_protect_server import UpvServer

LOGGER = udi_interface.LOGGER
SERVERDATA = json.load(open('server.json'))
VERSION = SERVERDATA['credits'][0]['version']

def get_profile_info(logger):
    pvf = 'profile/version.txt'
    try:
        with open(pvf) as f:
            pv = f.read().replace('\n', '')
    except Exception as err:
        logger.error('get_profile_info: failed to read  file {0}: {1}'.format(pvf,err), exc_info=True)
        pv = 0
    f.close()
    return { 'version': pv }

class Controller(udi_interface.Node):

    def __init__(self, polyglot):
        super(Controller, self).__init__(polyglot, primary, address, name)
        self.poly = polyglot
        self.name = 'UnifiProtect'
        self.queryON = False
        self.hb = 0
        self.unifi_host = ""
        self.unifi_port = ""
        self.unifi_userid = "" 
        self.unifi_password = ""

        polyglot.subscribe(polyglot.START, self.start, address)
        polyglot.subscribe(polyglot.CUSTOMPARAMS, self.parameterHandler)
        polyglot.subscribe(polyglot.POLL, self.poll)

        polyglot.ready()
        polyglot.addNode(self)
        
    def parameterHandler(self, params):
        self.poly.Notices.clear()
        try:
            if 'unifi_host' in params:
                self.unifi_host = params['unifi_host']
            else:
                self.unifi_host = ""
                
            if 'unifi_port' in params:
                self.unifi_port = params['unifi_port']
            else:
                self.unifi_port = "8443"    
            
            if 'unifi_userid' in params:
                self.unifi_userid = params['unifi_userid']
            else:
                self.unifi_userid = ""
            
            if 'unifi_password' in params:
                self.unifi_password = params['unifi_password']
            else:
                self.unifi_password = ""
             
            if self.unifi_host == "" or self.unifi_userid == "" or self.unifi_password == "" :
                LOGGER.error('Unifi requires \'unifi_host\' \'unifi_userid\' \'unifi_password\' parameters to be specified in custom configuration.')
                return False
            else:
                self.discover()
                
        except Exception as ex:
            LOGGER.error('Error starting Unifi NodeServer: %s', str(ex))
        
    def start(self):
        LOGGER.info('Started Unifi Protect for v2 NodeServer version %s', str(VERSION))
        self.setDriver('ST', 0)
    
    def poll(self, polltype):
        if 'shortPoll' in polltype:
            self.setDriver('ST', 1)
            for node in self.poly.nodes():
                if  node.queryON == True :
                    node.update()
        else:
            #self._newUsers()
            self.heartbeat()
    
    def query(self):
        for node in self.poly.nodes():
            node.reportDrivers()

    def heartbeat(self):
        LOGGER.debug('heartbeat: hb={}'.format(self.hb))
        if self.hb == 0:
            self.reportCmd("DON",2)
            self.hb = 1
        else:
            self.reportCmd("DOF",2)
            self.hb = 0

    def discover(self, *args, **kwargs):
        cams = asyncio.run(self._getDevices()) 
        
        for key,value in cams.items():
            name  = value["name"].replace("_","")
            myhash =  str(int(hashlib.md5(name.encode('utf8')).hexdigest(), 16) % (10 ** 8))
            if not self.poly.getNode(myhash):
                self.poly.addNode(Cam(self.poly,self.address,myhash,name,key ))
       
    def delete(self):
        LOGGER.info('Deleting Unifi')

    async def _getDevices (self) :
        #device = None
        session = ClientSession(cookie_jar=CookieJar(unsafe=True))

        # Log in to Unifi Protect
        unifiprotect = UpvServer(session, self.unifi_host, self.unifi_port,self.unifi_userid,self.unifi_password)
        await unifiprotect.ensure_authenticated()
        cams = await unifiprotect.update()
               
        await session.close()
        await unifiprotect.async_disconnect_ws()
        
        return cams 

    id = 'controller'
    commands = {
        'QUERY': query,
        'DISCOVER': discover,
    }
    drivers = [{'driver': 'ST', 'value': 1, 'uom': 2}]

class Cam(udi_interface.Node):

    def __init__(self, controller, primary, address, name,cameraId):

        super(Cam, self).__init__(controller, primary, address, name)
        self.queryON = True
        self.cameraId = cameraId

        controller.subscribe(controller.START, self.start, address)
        
    def start(self):
        pass

    def query(self):
        
        try :
            recordingMode = asyncio.run(self._getRecordingMode())
            if ( recordingMode == "never") :
                self.setDriver('GV2', 1)
            elif ( recordingMode == "motion") :
                self.setDriver('GV2', 2)
            elif ( recordingMode == "always") :
                self.setDriver('GV2', 3)
            elif ( recordingMode == "smartDetect") :
                self.setDriver('GV2', 4)
                
        except Exception as ex:
            LOGGER.error('query: %s', str(ex))
    
    def setRecordingMode(self,command):
        
        try :
            bLight = True
            intEffect = int(command.get('value'))
            if ( intEffect == 1 ):
                strMode = "never"
                bLight = False
            elif ( intEffect == 2 ):
                strMode = "motion"
            elif ( intEffect == 3 ):
                strMode = "always"
            elif ( intEffect == 4 ):
                strMode = "smartDetect"

            asyncio.run(self._setRecordingMode(strMode,bLight)) 
        
        except Exception as ex:
            LOGGER.error('setRecordingMode: %s', str(ex))
    
    async def _getRecordingMode (self) :
        recordingMode = None
        session = ClientSession(cookie_jar=CookieJar(unsafe=True))

        unifiprotect = UpvServer(session, self.parent.unifi_host, self.parent.unifi_port,self.parent.unifi_userid,self.parent.unifi_password)
        await unifiprotect.ensure_authenticated()
        
        cams = await unifiprotect.update()
        cam = cams[self.cameraId]
        recordingMode = cam["recording_mode"]
        
        await session.close()
        await unifiprotect.async_disconnect_ws()   
        
        return recordingMode
       
    async def _setRecordingMode (self, strMode, bLight) :
            
        session = ClientSession(cookie_jar=CookieJar(unsafe=True))

        unifiprotect = UpvServer(session, self.parent.unifi_host, self.parent.unifi_port,self.parent.unifi_userid,self.parent.unifi_password)
        await unifiprotect.ensure_authenticated()
        await unifiprotect.update()
        await unifiprotect.set_camera_recording(self.cameraId, strMode)
        await unifiprotect.set_device_status_light(self.cameraId, bLight, '')
        await session.close()
        await unifiprotect.async_disconnect_ws()
                
    drivers = [{'driver': 'GV2', 'value': 1, 'uom': 25}]

    id = 'UNIFI_CAM'
    commands = {'SET_RECORDING': setRecordingMode }

if __name__ == "__main__":
    try:
        polyglot = udi_interface.Interface([])
        polyglot.start()
        polyglot.updateProfile()
        polyglot.setCustomParamsDoc()
        Controller(polyglot, 'controller', 'controller', 'UnifiProtectNodeServer')
        polyglot.runForever()
    except (KeyboardInterrupt, SystemExit):
        sys.exit(0)
