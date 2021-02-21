# UniFi Device Network Presence Detection Polyglot V2 Node Server

![Build Status](https://travis-ci.org/therealmysteryman/udi-presenceUnifi-nodeserver.svg?branch=master)

This Poly provides an interface between Unifi Controller and Polyglot v2 server. 

## Installation

Installation instructions

You can install from Polyglot V2 store or manually :

1. cd ~/.polyglot/nodeservers
2. git clone https://github.com/therealmysteryman/udi-presenceUnifi-nodeserver.git
3. run ./install.sh to install the required dependency.
4. Add following custom variable :
    - unifi_host
    - unifi_port
    - unifi_userid
    - unifi_password
    - unifi_siteid 
    - mac_device -> comma delimited list of mac address of device to detect presence on the network.

## Source

1. Using this Python Library to control the Unifi - https://github.com/NickWaterton/Unifi-websocket-interface/blob/master/controller.py
2. Based on the Node Server Template - https://github.com/Einstein42/udi-poly-template-python

## Release Notes
