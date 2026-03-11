#!/bin/bash
# RESTCONF Commands to shutdown links: S4-S9, S9-S4
# Energy saving: 9.5%
# WARNING: These commands are NOT automatically executed

# Step 1
curl -u admin:admin -X GET -H "Content-Type: application/json" "http://192.168.10.22:8181/restconf/config/network-topology:network-topology/topology/topology-netconf/node/node4/yang-ext:mount/Cisco-IOS-XR-ifmgr-cfg:interface-configurations/interface-configuration/act/GigabitEthernet0%2F0%2F0%2F7" > put_GigabitEthernet0_0_0_7.json

# Step 2
curl -u admin:admin -X PUT -H "Content-Type: application/json" "http://192.168.10.22:8181/restconf/config/network-topology:network-topology/topology/topology-netconf/node/node4/yang-ext:mount/Cisco-IOS-XR-ifmgr-cfg:interface-configurations/interface-configuration/act/GigabitEthernet0%2F0%2F0%2F7" -d @put_GigabitEthernet0_0_0_7.json

# Step 3
curl -u admin:admin -X GET -H "Content-Type: application/json" "http://192.168.10.22:8181/restconf/config/network-topology:network-topology/topology/topology-netconf/node/node9/yang-ext:mount/Cisco-IOS-XR-ifmgr-cfg:interface-configurations/interface-configuration/act/GigabitEthernet0%2F0%2F0%2F3" > put_GigabitEthernet0_0_0_3.json

# Step 4
curl -u admin:admin -X PUT -H "Content-Type: application/json" "http://192.168.10.22:8181/restconf/config/network-topology:network-topology/topology/topology-netconf/node/node9/yang-ext:mount/Cisco-IOS-XR-ifmgr-cfg:interface-configurations/interface-configuration/act/GigabitEthernet0%2F0%2F0%2F3" -d @put_GigabitEthernet0_0_0_3.json

