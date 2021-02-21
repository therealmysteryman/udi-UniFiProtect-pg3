#!/usr/bin/env python3

"""
This is a NodeServer for Unifi Device Detection written by automationgeek (Jean-Francois Tremblay)
based on the NodeServer template for Polyglot v2 written in Python2/3 by Einstein.42 (James Milne) milne.james@gmail.com
"""

import polyinterface
import hashlib
import warnings 
import time
import json
import sys
from urllib.parse import quote
from copy import deepcopy
from unifi_api_controller import Controller as unifictl



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
        self.name = 'UnifiCtrl'
        self.queryON = False
        self.hb = 0
        self.unifi_host = ""
        self.unifi_port = ""
        self.unifi_userid = "" 
        self.unifi_password = ""
        self.unifi_siteid = ""
        self.mac_device = ""

    def start(self):
        LOGGER.info('Started Unifi for v2 NodeServer version %s', str(VERSION))
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
            
            if 'unifi_siteid' in self.polyConfig['customParams']:
                self.unifi_siteid = self.polyConfig['customParams']['unifi_siteid']
            else:
                self.unifi_siteid = "default"  
                
            if 'mac_device' in self.polyConfig['customParams']:
                self.mac_device = self.polyConfig['customParams']['mac_device']
            else:
                self.mac_device = ""      
                                
            if self.unifi_host == "" or self.unifi_userid == "" or self.unifi_password == "" or self.mac_device == "" :
                LOGGER.error('Unifi requires \'unifi_host\' \'unifi_userid\' \'unifi_password\' \'mac_device\' parameters to be specified in custom configuration.')
                return False
            else:
                self.check_profile()
                self.discover()
                
        except Exception as ex:
            LOGGER.error('Error starting Unifi NodeServer: %s', str(ex))
           
    def shortPoll(self):
        self.setDriver('ST', 1)
        for node in self.nodes:
            if  self.nodes[node].queryON == True :
                self.nodes[node].update()
                
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
        
        ctrl = unifictl(self.unifi_host,self.unifi_userid,self.unifi_password,self.unifi_port,site_id=self.unifi_siteid,ssl_verify=False)
        
        for netdevice in self.mac_device.split(','):
            name =  netdevice.replace(":","") 
            self.addNode(NetDevice(self,self.address,name,name,ctrl,netdevice ))

    def delete(self):
        LOGGER.info('Deleting Unifi')

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

class NetDevice(polyinterface.Node):

    def __init__(self, controller, primary, address, name,ctrl, mac):

        super(NetDevice, self).__init__(controller, primary, address, name)
        self.queryON = True
        self.deviceMac = mac
        self.unifiCtrl = ctrl

    def start(self):
        self.update()

    def query(self):
        self.reportDrivers()
        
    def update(self):
        try :
            if ( 'essid' in self.unifiCtrl.get_client(self.deviceMac) ) :
                self.setDriver('GV1',1)
            else:
                self.setDriver('GV1',0)
            
        except Exception as ex :
            self.setDriver('GV1',0)
            LOGGER.info('update: %s', str(ex))
            
    drivers = [{'driver': 'GV1', 'value': 0, 'uom': 2}]

    id = 'UNIFI_DEVICE'
    commands = {
                }

if __name__ == "__main__":
    try:
        polyglot = polyinterface.Interface('UnifiNodeServer')
        polyglot.start()
        control = Controller(polyglot)
        control.runForever()
    except (KeyboardInterrupt, SystemExit):
        sys.exit(0)
