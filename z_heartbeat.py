#!/usr/bin/env python3
# coding: utf-8 -*-
#
# Author: zaraki673 & pipiche38
#
"""
    Module: z_heartbeat.py

    Description: Manage all actions done during the onHeartbeat() call

"""

import Domoticz
import binascii
import time
import struct
import json
import queue

import z_var
import z_output
import z_tools
import z_domoticz
import z_LQI

HEARBEAT_VALUE = 5

def processKnownDevices( self, NWKID ):

    # Check if Node Descriptor was run ( this could not be the case on early version)
    intHB = int( self.ListOfDevices[NWKID]['Heartbeat'])
    if  intHB == ( 28 // HEARBEAT_VALUE):
        if not self.ListOfDevices[NWKID].get('PowerSource'):    # Looks like PowerSource is not available, let's request a Node Descriptor
            z_output.sendZigateCmd(self,"0042", str(NWKID) )    # Request a Node Descriptor

    if ( intHB % ( 60 // HEARBEAT_VALUE) ) == 0 or ( intHB == ( 24 // HEARBEAT_VALUE)):
        if  'PowerSource' in self.ListOfDevices[NWKID]:        # Let's check first that the field exist, if not it will be requested at Heartbeat == 12 (see above)
            if self.ListOfDevices[NWKID]['PowerSource'] == 'Main':    #  Only for device receiving req on idle
                for tmpEp in self.ListOfDevices[NWKID]['Ep']:    # Request ReadAttribute based on Cluster 
                    if "0702" in self.ListOfDevices[NWKID]['Ep'][tmpEp]:    # Cluster Metering
                        z_output.ReadAttributeRequest_0702(self, NWKID )
                    #if "0008" in self.ListOfDevices[NWKID]['Ep'][tmpEp]:    # Cluster LvlControl
                    #    z_output.ReadAttributeRequest_0008(self, NWKID )
                    #if "000C" in self.ListOfDevices[NWKID]['Ep'][tmpEp]:    # Cluster Xiaomi
                    #    z_output.ReadAttributeRequest_000C(self, NWKID )
                    #if "0006" in self.ListOfDevices[NWKID]['Ep'][tmpEp]:    # Cluster On/off
                    #    z_output.ReadAttributeRequest_0006(self, NWKID )
                    #if "0000" in self.ListOfDevices[NWKID]['Ep'][tmpEp]:    # Cluster Power
                    #    z_output.ReadAttributeRequest_0000(self, NWKID )
                    #if "0001" in self.ListOfDevices[NWKID]['Ep'][tmpEp]:    # Cluster Power
                    #    z_output.ReadAttributeRequest_0001(self, NWKID )
                    #if "0300" in self.ListOfDevices[NWKID]['Ep'][tmpEp]:    # Color Temp
                    #    z_output.ReadAttributeRequest_0300(self, NWKID )
                    pass

    
def processNotinDBDevices( self, Devices, NWKID , status , RIA ):

    # 0x004d is a device annoucement.
    # Usally we get Network Address (short address) and IEEE
    if status == "004d" and self.ListOfDevices[NWKID]['Heartbeat'] <= "4":
        Domoticz.Log("processNotinDBDevices - Discovery process for " + str(NWKID) + " Info: " + str(self.ListOfDevices[NWKID]) )
        # We should check if the device has not been already created via IEEE
        if z_tools.IEEEExist( self, self.ListOfDevices[NWKID]['IEEE'] ) == False:
            Domoticz.Log("processNotinDBDevices - new device discovered request Node Descriptor for: " +str(NWKID) )
            self.ListOfDevices[NWKID]['Heartbeat'] = "0"
            self.ListOfDevices[NWKID]['Status'] = "0045"
            z_output.sendZigateCmd(self,"0045", str(NWKID))     # Request list of EPs
            z_output.ReadAttributeRequest_0000(self, NWKID )    # Basic Cluster readAttribute Request
            z_output.sendZigateCmd(self,"0042", str(NWKID))     # Request a Node Descriptor
            return
        else:
            for dup in self.ListOfDevices:
                if self.ListOfDevices[NWKID]['IEEE'] == self.ListOfDevices[dup]['IEEE'] and self.ListOfDevices[dup]['Status'] == "inDB":
                    Domoticz.Error("onHearbeat - Device: " + str(NWKID) + "already known under IEEE: " +str(self.ListOfDevices[NWKID]['IEEE'] ) 
                                        + " Duplicate of " + str(dup) )
                    Domoticz.Error("onHearbeat - Please check the consistency of the plugin database and domoticz database.")
                    self.ListOfDevices[NWKID]['Status']="DUP"
                    self.ListOfDevices[NWKID]['Heartbeat']="0"
                    self.ListOfDevices[NWKID]['RIA']="99"
                    break
    # 0x8045 is providing the list of active EPs
    #we will so request EP descriptor for each of them
    if status == "8045" and self.ListOfDevices[NWKID]['Heartbeat'] <= "4":    # Status is set by Decode8045
        Domoticz.Log("onHeartbeat - new device discovered 0x8045 received " + NWKID)
        if self.ListOfDevices[NWKID]['Model'] == '':
            z_output.ReadAttributeRequest_0000(self, NWKID )      # Basic Cluster readAttribute Request
        self.ListOfDevices[NWKID]['Heartbeat'] = "0"
        self.ListOfDevices[NWKID]['Status'] = "0043"
        for cle in self.ListOfDevices[NWKID]['Ep']:
            Domoticz.Log("onHeartbeat - new device discovered request Simple Descriptor 0x0043 and wait for 0x8043 for EP " + cle + ", of: " + NWKID)
            z_output.sendZigateCmd(self,"0043", str(NWKID)+str(cle))    
        return
        z_output.sendZigateCmd(self,"0042", str(NWKID))     # Request a Node Descriptor


    waitForDomoDeviceCreation = 0
    if status == "8043":
        # In case we received 0x8043, we might want to check if there is a 0x0300 cluster. 
        # In that case, that is a Color Bulbe and we might want to ReadAttribute in ordert o discover what is the ColorMode .
        waitForDomoDeviceCreation = 0
        reqColorModeAttribute = 0

        for iterEp in self.ListOfDevices[NWKID]['Ep']:
            if '0300' not in self.ListOfDevices[NWKID]['Ep'][iterEp]:
                continue
            else:
                if 'ColorInfos' in self.ListOfDevices[NWKID]:
                    if 'ColorMode' in self.ListOfDevices[NWKID]['ColorInfos']:
                        waitForDomoDeviceCreation = 0
                        reqColorModeAttribute = 0
                        break
                    else:
                        waitForDomoDeviceCreation = 1
                        reqColorModeAttribute = 1
                        break
                else:
                    waitForDomoDeviceCreation = 1
                    reqColorModeAttribute = 1
                    break

        if reqColorModeAttribute == 1:
            self.ListOfDevices[NWKID]['RIA']=str(int(self.ListOfDevices[NWKID]['RIA'])+1)
            z_output.ReadAttributeRequest_0300(self, NWKID )


    # Timeout management
    if (status == "004d" or status == "0045") and self.ListOfDevices[NWKID]['Heartbeat']>="6":
        Domoticz.Log("onHeartbeat - new device %s discovered but no processing done, let's Timeout at %s " %(status, NWKID))
        self.ListOfDevices[NWKID]['RIA']=str(int(self.ListOfDevices[NWKID]['RIA'])+1)
        self.ListOfDevices[NWKID]['Heartbeat']="0"
        self.ListOfDevices[NWKID]['Status']="0045"
        z_output.sendZigateCmd(self,"0045", str(NWKID))     # Request list of EPs
        z_output.ReadAttributeRequest_0000(self, NWKID)      # Basic Cluster readAttribute Request
        z_output.sendZigateCmd(self,"0042", str(NWKID))     # Request a Node Descriptor
        return

    if (status == "8045" or status == "0043") and self.ListOfDevices[NWKID]['Heartbeat']>="6":
        Domoticz.Log("onHeartbeat - new device %s discovered but no processing done, let's Timeout at %s " %(status, NWKID))
        self.ListOfDevices[NWKID]['RIA']=str(int(self.ListOfDevices[NWKID]['RIA'])+1)
        self.ListOfDevices[NWKID]['Heartbeat']="0"
        self.ListOfDevices[NWKID]['Status']="0043"
        for cle in self.ListOfDevices[NWKID]['Ep']:
            Domoticz.Log("onHeartbeat - new device discovered request Simple Descriptor 0x0043 and wait for 0x8043 for EP " + cle + ", of: " + NWKID)
            z_output.sendZigateCmd(self,"0043", str(NWKID)+str(cle))    
        return

    if status!="UNKNOW" and self.ListOfDevices[NWKID]['RIA'] > "5":  # We have done several retry
        Domoticz.Log("onHeartbeat - new device %s discovered but no processing done, let's Timeout at %s " %(status, NWKID))
        self.ListOfDevices[NWKID]['Heartbeat']="0"
        self.ListOfDevices[NWKID]['Status']="UNKNOW"
        Domoticz.Error("processNotinDB - not able to find response from " +str(NWKID) + " stop process at " +str(status) )
        Domoticz.Error("processNotinDB - we are not able to Create this Device " +str(NWKID) + " stop process at " +str(status) )

    #ZLL
    #Lightning devices
    # ZDeviceID = 0000 >> On/Off light
    # ZDeviceID = 0010 >> on/off light but plug
    # ZDeviceID = 0100 >> Dimable but no color
    # ZDeviceID = 0110 >> Dimable but no color and plug
    # ZDeviceID = 0200 >> Color light or shutter
    # ZDeviceID = 0220 >> Temperature Color change
    # ZDeviceID = 0210 >> Hue/Extended Color change
    #Controllers devices
    # ZDeviceID = 0800 >> Color controler
    # ZDeviceID = 0810 >> Color scene controler
    # ZDeviceID = 0820 >> Non color controler
    # ZDeviceID = 0830 >> Non color scene controler
    # ZDeviceID = 0840 >> Control bridge
    # ZDeviceID = 0850 >> on/off sensor
    
    #ZHA
    #Device
    # ZDeviceID = 0000 >> On/Off switch
    # ZDeviceID = 0001 >> Level control switch
    # ZDeviceID = 0002 >> on/off output
    # ZDeviceID = 0003 >> Level contro output
    # ZDeviceID = 0004 >> Scene selector
    # ZDeviceID = 0005 >> Configuration tool
    # ZDeviceID = 0006 >> Remote control
    # ZDeviceID = 0007 >> Combined interface
    # ZDeviceID = 0008 >> Range extender
    # ZDeviceID = 0009 >> Mains Power Outlet
    # ZDeviceID = 000A >> Door lock
    # ZDeviceID = 000B >> Door lock controler
    # ZDeviceID = 000C >> HSimple sensor
    # ZDeviceID = 000D >> Consumption awarness Device
    # ZDeviceID = 0050 >> Home gateway
    # ZDeviceID = 0051 >> Smart plug
    # ZDeviceID = 0052 >> White goods
    # ZDeviceID = 0053 >> Meter interface
    # ZDeviceID = 0100 >> On/Off light
    # ZDeviceID = 0101 >> Dimable light
    # ZDeviceID = 0102 >> Color dimable light
    # ZDeviceID = 0103 >> on/off light
    # ZDeviceID = 0104 >> Dimmer switch
    # ZDeviceID = 0105 >> Color Dimmer switch
    # ZDeviceID = 0106 >> Light sensor
    # ZDeviceID = 0107 >> Occupancy sensor
    # ZDeviceID = 010a >> Unknow: plug legrand
    # ZDeviceID = 0200 >> Shade
    # ZDeviceID = 0201 >> Shade controler
    # ZDeviceID = 0202 >> Window covering device
    # ZDeviceID = 0203 >> Window Covering controler
    # ZDeviceID = 0300 >> Heating/cooling Unit
    # ZDeviceID = 0301 >> Thermostat
    # ZDeviceID = 0302 >> Temperature sensor
    # ZDeviceID = 0303 >> Pump
    # ZDeviceID = 0304 >> Pump controler
    # ZDeviceID = 0305 >> Pressure sensor
    # ZDeviceID = 0306 >> flow sensor
    # ZDeviceID = 0307 >> Mini split AC
    # ZDeviceID = 0400 >> IAS Control and indicating equipement 
    # ZDeviceID = 0401 >> IAS Ancillary Control Equipement
    # ZDeviceID = 0402 >> IAS zone
    # ZDeviceID = 0403 >> IAS Warning device
    
    # ProfileID = c05e >> ZLL: ZigBee Light Link
    # ProfileID = 0104 >> ZHA: ZigBee Home Automation
    # ProfileID = a1e0 >> Philips Hue ???
    # ProfileID =      >> SEP: Smart Energy Profile
    # There is too ZBA, ZTS, ZRS, ZHC but I haven't find information for them
    
    #ZigBee HA contains (nearly?) everything in ZigBee Light Link

    # If we are in status = 0x8043 we have received EPs descriptors
    # If we have Model we might be able to identify the device with it's model
    # In case where self.pluginconf.storeDiscoveryFrames is set (1) then we force the full process and so wait for 0x8043
    if ( waitForDomoDeviceCreation != 1 and  self.pluginconf.allowStoreDiscoveryFrames == 0 and status != "UNKNOW" and status != "DUP") or \
            ( waitForDomoDeviceCreation != 1 and self.pluginconf.allowStoreDiscoveryFrames == 1 and status == "8043" ):
        if ( self.ListOfDevices[NWKID]['Status']=="8043" or self.ListOfDevices[NWKID]['Model']!= {} ):
            #We will try to create the device(s) based on the Model , if we find it in DeviceConf or against the Cluster
            Domoticz.Log("processNotinDBDevices - Let's try to create the device with what we have: " +str(NWKID) + " => " +str(self.ListOfDevices[NWKID]) )

            IsCreated=False
            x=0
            # Let's check if the IEEE is not known in Domoticz
            for x in Devices:
                if self.ListOfDevices[NWKID].get('IEEE'):
                    if Devices[x].DeviceID == str(self.ListOfDevices[NWKID]['IEEE']):
                        if self.pluginconf.forceCreationDomoDevice == 1:
                            Domoticz.Log("processNotinDBDevices - Devices already exist. "  + Devices[x].Name + " with " + str(self.ListOfDevices[NWKID]) )
                            Domoticz.Error("processNotinDBDevices - ForceCreationDevice enable, we continue")
                        else:
                            IsCreated = True
                            Domoticz.Error("processNotinDBDevices - Devices already exist. "  + Devices[x].Name + " with " + str(self.ListOfDevices[NWKID]) )
                            Domoticz.Error("processNotinDBDevices - Please cross check the consistency of the Domoticz and Plugin database.")
                            break

            if IsCreated == False:
                Domoticz.Log("onHeartbeat - Creating device in Domoticz: " + str(NWKID) + " with: " + str(self.ListOfDevices[NWKID]) )
                z_domoticz.CreateDomoDevice(self, Devices, NWKID)
                z_output.processConfigureReporting( self, NWKID )  # Configure Reporting for that device

        #end if ( self.ListOfDevices[NWKID]['Status']=="8043" or self.ListOfDevices[NWKID]['Model']!= {} )
    #end ( self.pluginconf.storeDiscoveryFrames == 0 and status != "UNKNOW" and status != "DUP")  or (  self.pluginconf.storeDiscoveryFrames == 1 and status == "8043" )
    

def processListOfDevices( self , Devices ):
    # Let's check if we do not have a command in TimeOut
    self.ZigateComm.checkTOwaitFor()

    for NWKID in list(self.ListOfDevices):
        # If this entry is empty, then let's remove it .
        if len(self.ListOfDevices[NWKID]) == 0:
            Domoticz.Debug("Bad devices detected (empty one), remove it, adr:" + str(NWKID))
            del self.ListOfDevices[NWKID]
            continue
            
        status=self.ListOfDevices[NWKID]['Status']
        RIA=int(self.ListOfDevices[NWKID]['RIA'])
        self.ListOfDevices[NWKID]['Heartbeat']=str(int(self.ListOfDevices[NWKID]['Heartbeat'])+1)

        ########## Known Devices 
        if status == "inDB": 
            processKnownDevices( self , NWKID )

        if status == "Left":
            # Device has sent a 0x8048 message annoucing its departure (Leave)
            # Most likely we should receive a 0x004d, where the device come back with a new short address
            # For now we will display a message in the log every 1'
            # We might have to remove this entry if the device get not reconnected.
            if (( int(self.ListOfDevices[NWKID]['Heartbeat']) % 36 ) and  int(self.ListOfDevices[NWKID]['Heartbeat']) != 0) == 0:
                Domoticz.Log("processListOfDevices - Device: " +str(NWKID) + " is in Status = 'Left' for " +str(self.ListOfDevices[NWKID]['Heartbeat']) + "HB" )
                # Let's check if the device still exist in Domoticz
                fnd = True
                for Unit in Devices:
                    if self.ListOfDevices[NWKID]['IEEE'] == Devices[Unit].DeviceID:
                        Domoticz.Debug("processListOfDevices - %s  is still connected cannot remove. NwkId: %s IEEE: %s " \
                                %(Devices[Unit].Name, NWKID, self.ListOfDevices[NWKID]['IEEE']))
                        fnd = True
                        break
                else: #We browse the all Devices and didn't find any IEEE.
                    Domoticz.Log("processListOfDevices - No corresponding device in Domoticz for %s " %( NWKID, self.ListOfDevices[NWKID]['IEEE']))
                    fnd = False

                if not fnd:
                    # Not devices found in Domoticz, so we are safe to remove it from Plugin
                    if self.ListOfDevices[NWKID]['IEEE'] in self.IEEE2NWK:
                        Domoticz.Log("processListOfDevices - Removing %s / %s from IEEE2NWK." %(self.ListOfDevices[NWKID]['IEEE'], NWKID))
                        del self.IEEE2NWK[self.ListOfDevices[NWKID]['IEEE']]
                    Domoticz.Log("processListOfDevices - Removing the entry %s from ListOfDevice" %(NWKID))
                    z_tools.removeNwkInList( self, NWKID)

        elif status != "inDB" and status != "UNKNOW":
            # Discovery process 0x004d -> 0x0042 -> 0x8042 -> 0w0045 -> 0x8045 -> 0x0043 -> 0x8043
            processNotinDBDevices( self , Devices, NWKID, status , RIA )

    #end for key in ListOfDevices

    # LQI Scanner
    #    - LQI = 0 - no scanning at all otherwise delay the scan by n x 10s
    
    if self.pluginconf.logLQI != 0 and \
            self.HeartbeatCount > (( 120 + self.pluginconf.logLQI) // HEARBEAT_VALUE):
        if self.ZigateComm.loadTransmit() < 5 :
            z_LQI.LQIcontinueScan( self )

    if self.HeartbeatCount == 4:
        # Trigger Conifre Reporting to eligeable decices
        z_output.processConfigureReporting( self )
    
    if self.pluginconf.networkScan != 0 and \
            (self.HeartbeatCount == ( 120 // HEARBEAT_VALUE ) or (self.HeartbeatCount % ((300+self.pluginconf.networkScan ) // HEARBEAT_VALUE )) == 0) :
        z_output.NwkMgtUpdReq( self, ['11','12','13','14','15','16','17','18','19','20','21','22','23','24','25','26'] , mode='scan')


    return True



