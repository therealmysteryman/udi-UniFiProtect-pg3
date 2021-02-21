#!/usr/bin/env python3

"""
This is a NodeServer for Unifi Protect written by automationgeek (Jean-Francois Tremblay)
based on the NodeServer template for Polyglot v2 written in Python2/3 by Einstein.42 (James Milne) milne.james@gmail.com
"""

import polyinterface
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

LOGGER = polyinterface.LOGGER
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

class Controller(polyinterface.Controller):

    def __init__(self, polyglot):
        super(Controller, self).__init__(polyglot)
        self.name = 'UnifiProtect'
        self.queryON = False
        self.hb = 0
        self.unifi_host = ""
        self.unifi_port = ""
        self.unifi_userid = "" 
        self.unifi_password = ""

    def start(self):
        LOGGER.info('Started Unifi Protect for v2 NodeServer version %s', str(VERSION))
        self.setDriver('ST', 0)
        try:
            if 'unifi_host' in self.polyConfig['customParams']:
                self.unifi_host = self.polyConfig['customParams']['unifi_host']
            else:
                self.unifi_host = ""
                
            if 'unifi_port' in self.polyConfig['customParams']:
                self.unifi_port = self.polyConfig['customParams']['unifi_port']
            else:
                self.unifi_port = "8443"    
            
            if 'unifi_userid' in self.polyConfig['customParams']:
                self.unifi_userid = self.polyConfig['customParams']['unifi_userid']
            else:
                self.unifi_userid = ""
            
            if 'unifi_password' in self.polyConfig['customParams']:
                self.unifi_password = self.polyConfig['customParams']['unifi_password']
            else:
                self.unifi_password = ""
                              
            if self.unifi_host == "" or self.unifi_userid == "" or self.unifi_password == "" :
                LOGGER.error('Unifi requires \'unifi_host\' \'unifi_userid\' \'unifi_password\' parameters to be specified in custom configuration.')
                return False
            else:
                self.check_profile()
                self.discover()
                
        except Exception as ex:
            LOGGER.error('Error starting Unifi NodeServer: %s', str(ex))
           
    def shortPoll(self):
        self.setDriver('ST', 1)
        #for node in self.nodes:
        #    if  self.nodes[node].queryON == True :
        #        self.nodes[node].update()
                
    def longPoll(self):
        self.heartbeat()
        
    def query(self):
        for node in self.nodes:
            self.nodes[node].reportDrivers()

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
            self.addNode(Cam(self,self.address,myhash,name,key ))
       
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
        
    def check_profile(self):
        self.profile_info = get_profile_info(LOGGER)
        # Set Default profile version if not Found
        cdata = deepcopy(self.polyConfig['customData'])
        LOGGER.info('check_profile: profile_info={0} customData={1}'.format(self.profile_info,cdata))
        if not 'profile_info' in cdata:
            cdata['profile_info'] = { 'version': 0 }
        if self.profile_info['version'] == cdata['profile_info']['version']:
            self.update_profile = False
        else:
            self.update_profile = True
            self.poly.installprofile()
        LOGGER.info('check_profile: update_profile={}'.format(self.update_profile))
        cdata['profile_info'] = self.profile_info
        self.saveCustomData(cdata)

    def install_profile(self,command):
        LOGGER.info("install_profile:")
        self.poly.installprofile()

    id = 'controller'
    commands = {
        'QUERY': query,
        'DISCOVER': discover,
        'INSTALL_PROFILE': install_profile,
    }
    drivers = [{'driver': 'ST', 'value': 1, 'uom': 2}]

class Cam(polyinterface.Node):

    def __init__(self, controller, primary, address, name,cameraId):

        super(Cam, self).__init__(controller, primary, address, name)
        self.queryON = True
        self.cameraId = cameraId

    def start(self):
        pass

    def query(self):
        self.reportDrivers()
    
    def setRecordingMode(self,command):
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
    
    
    async def _setRecordingMode (self, strMode, bLight) :
            
        session = ClientSession(cookie_jar=CookieJar(unsafe=True))

        unifiprotect = UpvServer(session, self.unifi_host, self.unifi_port,self.unifi_userid,self.unifi_password)
        await unifiprotect.ensure_authenticated()
        await unifiprotect.update()
        await set_camera_recording(self, self.cameraId, strMode)
        await set_device_status_light( self, self.cameraId, strMode, 'light')
        await session.close()
        await unifiprotect.async_disconnect_ws()
                
    drivers = [{'driver': 'GV2', 'value': 1, 'uom': 25}]

    id = 'UNIFI_CAM'
    commands = {'SET_RECORDING': setRecordingMode }

if __name__ == "__main__":
    try:
        polyglot = polyinterface.Interface('UnifiProtectNodeServer')
        polyglot.start()
        control = Controller(polyglot)
        control.runForever()
    except (KeyboardInterrupt, SystemExit):
        sys.exit(0)
