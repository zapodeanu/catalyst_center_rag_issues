#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""

Copyright (c) 2026 Cisco and/or its affiliates.

This software is licensed to you under the terms of the Cisco Sample
Code License, Version 1.1 (the "License"). You may obtain a copy of the
License at

               https://developer.cisco.com/docs/licenses

All use of the material herein must be in accordance with the terms of
the License. All rights not expressly granted by the License are
reserved. Unless required by applicable law or agreed to separately in
writing, software distributed under the License is distributed on an "AS
IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express
or implied.

"""

__author__ = "Gabriel Zapodeanu, Principal TME"
__email__ = "gzapodea@cisco.com"
__version__ = "0.1.0"
__copyright__ = "Copyright (c) 2026 Cisco and/or its affiliates."
__license__ = "Cisco Sample Code License, Version 1.1"

import argparse
import json
import logging
import os
import time
import urllib3
import yaml

from datetime import datetime
from catalystcentersdk import api
from dotenv import load_dotenv
from urllib3.exceptions import InsecureRequestWarning  # for insecure https warnings

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(BASE_DIR, "environment.env")
load_dotenv(ENV_PATH)

CC_URL = os.getenv('CC_URL')
CC_USER = os.getenv('CC_USER')
CC_PASS = os.getenv('CC_PASS')

APPS_PATH = os.getenv('APPS_PATH')
DATASET = os.getenv('DATASET')

os.environ['TZ'] = 'America/Los_Angeles'  # define the timezone for PST
time.tzset()  # adjust the timezone, more info https://help.pythonanywhere.com/pages/SettingTheTimezone/

urllib3.disable_warnings(InsecureRequestWarning)  # disable insecure https warnings

# logging, debug level, to file {application_run.log}
logging.basicConfig(level=logging.INFO)


def main():
    """
    This application will automate network troubleshooting of network devices using Catalyst Center APIs. It will
    require one parameter, the Issue unique identifier.
    The application could run as a pipeline, ar part of the GenAI Troubleshooting App Stack.
    It will collect the:
    - issue details
    - device details
    - compliance
    - physical topology
    - execute Assurance suggested actions
    - identify the type of issue
    - execute all commands from troubleshooting knowledge base that match the the issue type
    :return:
    """

    # logging basic
    logging.basicConfig(level=logging.INFO)

    current_time = str(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    logging.info(' App "Network Troubleshooting.py" run start, ' + current_time)

    # parse the input arguments
    parser = argparse.ArgumentParser(description="A script that accepts one argument")
    parser.add_argument("assuranceIssueId", help="The Assurance issue Id")

    args = parser.parse_args()
    issue_id = args.assuranceIssueId

    logging.info(' The Assurance issue Id received is: ' + issue_id)

    os.chdir(APPS_PATH + '/' + DATASET)

    # create a Catalyst Center connection object to use the Python SDK
    cc_api = api.CatalystCenterAPI(username=CC_USER, password=CC_PASS,
                                       base_url=CC_URL, version='2.3.7.9', verify=False)

    # retrieve the issue enrichment details
    headers = {'entity_type': 'issue_id', 'entity_value': issue_id}
    issue_details = cc_api.issues.get_issue_enrichment_details(headers=headers)
    device_id = issue_details['issueDetails']['issue'][0]['deviceId']
    issue_description = issue_details['issueDetails']['issue'][0]['issueDescription']
    issue_name = issue_details['issueDetails']['issue'][0]['issueName'].replace('_', '-')
    issue_timestamp = issue_details['issueDetails']['issue'][0]['issueTimestamp']/1000
    issue_localtime = datetime.fromtimestamp(issue_timestamp).strftime('%c')
    issue_summary = issue_details['issueDetails']['issue'][0]['issueSummary']
    issue_priority = issue_details['issueDetails']['issue'][0]['issuePriority']
    issue_severity = issue_details['issueDetails']['issue'][0]['issueSeverity']

    # retrieve the device details
    device_details = cc_api.devices.get_device_detail(identifier='uuid', search_by=device_id)
    device_hostname = device_details['response']['nwDeviceName']
    device_management_ip_address = device_details['response']['managementIpAddr']
    device_serial_number = device_details['response']['serialNumber']
    device_health = device_details['response']['overallHealth']
    device_role = device_details['response']['nwDeviceRole']
    device_family = device_details['response']['platformId']
    device_software = device_details['response']['softwareVersion']
    device_reachable = device_details['response']['communicationState']
    device_location = device_details['response']['location']

    # log issue details
    logging.info('\n--------------------------------------------------------------------\n')
    issue_details_data = 'The device: ' + device_hostname + ' issue details'
    issue_details_data += '\n   Severity: ' + issue_severity
    issue_details_data += '\n   Priority: ' + issue_priority
    issue_details_data += '\n   Issue name: ' + issue_name
    issue_details_data += '\n   Summary: ' + issue_summary
    issue_details_data += '\n   Description: ' + issue_description
    issue_details_data += '\n   Timestamp: ' + issue_localtime
    issue_details_link = CC_URL + '/dna/assurance/issueDetails?issueId=' + issue_id
    issue_details_data += '\n   Issue Details: ' + issue_details_link
    logging.info(issue_details_data)

    # log device details
    logging.info('\n--------------------------------------------------------------------\n')
    device_details_data = 'The device: ' + device_hostname + ' details'
    device_details_data += '\n   Hostname: ' + device_hostname
    device_details_data += '\n   Location: ' + device_location
    device_details_data += '\n   Device Role: ' + device_role
    device_details_data += '\n   Device Id: ' + device_id
    device_details_data += '\n   Reachability: ' + device_reachable
    device_details_data += '\n   Health: ' + str(device_health)
    device_details_data += '\n   Management IP Address: ' + device_management_ip_address
    device_details_data += '\n   Serial Number: ' + device_serial_number
    device_details_data += '\n   Family: ' + device_family
    device_details_data += '\n   Software: ' + device_software
    logging.info(device_details_data)

    # save to issue and device details to DATASET folder
    with open(device_hostname + '_' + issue_name + '_issue-details.txt', 'w') as f:
        f.write(issue_details_data)
    with open(device_hostname + '_' + issue_name + '_device-details.txt', 'w') as f:
        f.write(device_details_data)

    # retrieve device compliance
    logging.info('\n--------------------------------------------------------------------\n')
    compliance_response = cc_api.compliance.compliance_details_of_device(device_uuid=device_id)
    compliance_status = compliance_response['response']
    compliance_status_data = 'The device: ' + device_hostname + ' compliance status'
    # logging the device compliance
    for compliance in compliance_status:
        compliance_status_data += '\n    ' + compliance['complianceType'] + ' status: ' + compliance['status']
    logging.info(compliance_status_data)

    # save to compliance to DATASET folder
    with open(APPS_PATH + '/DATASET/' + device_hostname + '_' + issue_name + '_compliance.txt', 'w') as f:
        f.write(compliance_status_data)

    # retrieve the device topology
    logging.info('\n--------------------------------------------------------------------\n')
    logging.info(' Device topology data started')
    headers = {'entity_type': 'device_id', 'entity_value': device_id}
    topology_response = cc_api.devices.get_device_enrichment_details(headers=headers)
    topology_data = topology_response[0]['deviceDetails']['neighborTopology'][0]['nodes']
    topology_nodes = []
    for node in topology_data:
        topology_nodes.append(device_hostname + ' connected with ' + node['name'] + ', IP address: ' + node['ip'])
    # save device topology to JSON formatted file
    with open(APPS_PATH + '/DATASET/' + device_hostname + '_' + issue_name + '_topology.txt', 'w') as f:
        f.write('This is the device ' + device_hostname + ' topology, connected with other devices and their IP address\n')
        f.write('\n'.join(topology_nodes) + '\n') # write each node on one line
    logging.info(topology_nodes)
    logging.info(' Saved the device topology')

    # execute suggested actions
    suggested_actions_response = cc_api.issues.execute_suggested_actions_commands(entity_type='issue_id', entity_value=issue_id)
    execution_id = suggested_actions_response['executionId']

    # check for execution to complete
    logging.info('\n--------------------------------------------------------------------\n')
    logging.info(' Suggested actions execution started')
    execution_status = 'IN_PROGRESS'
    suggested_actions_data = 'The device: ' + device_hostname + ' Suggested actions'
    time.sleep(10)
    while execution_status == 'IN_PROGRESS':
        execution_status_response = cc_api.task.get_business_api_execution_details(execution_id=execution_id)
        execution_status = execution_status_response['status']
        time.sleep(10)

    if execution_status != 'SUCCESS':
        logging.info(' Suggested actions execution failed')
    else:
        logging.info(' Suggested actions execution completed')
        suggested_actions_output = execution_status_response['bapiSyncResponse']
        status_json = json.loads(suggested_actions_output)

        # logging suggested actions executions
        for item in status_json:
            suggested_actions_data += '\n!'
            suggested_actions_data += '\n   ' + item['actionInfo']
            suggested_actions_data += '\n   Device: ' + item['hostname']
            suggested_actions_data += '\n   Command: ' + item['command']
            command_output = item['commandOutput']
            output = command_output[item['command']]
            suggested_actions_data += '\n   Command output: \n' + output
        logging.info(suggested_actions_data)
        # save to suggested actions execution data to DATASET folder
        with open(APPS_PATH + '/DATASET/' + device_hostname + '_' + issue_name + '_suggested-actions.txt', 'w') as f:
            f.write(suggested_actions_data)

    # knowledge base pull CLI commands and execution
    logging.info('\n--------------------------------------------------------------------\n')
    knowledgebase_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'troubleshooting_knowledgebase.yml')
    with open(knowledgebase_path, 'r') as file:
        knowledgebase = yaml.safe_load(file)

    # parse the input data
    cli_commands = knowledgebase[issue_name]['commands']
    logging.info(' Knowledgebase CLI commands:')
    for command in cli_commands:
        logging.info('    ' + command)
    logging.info('  ')

    # execute knowledge base commands, one at a time
    logging.info(' Knowledgebase commands execution started')
    for command in cli_commands:
        command_runner_response = cc_api.command_runner.run_read_only_commands_on_devices_to_get_their_real_time_configuration(deviceUuids=[device_id], commands=[command])
        task_id = command_runner_response['response']['taskId']
        logging.info(' Task Id: ' + task_id)

        # check for task to complete
        end_time = ''
        time.sleep(1)
        while end_time == '':
            task_status_response = cc_api.task.get_task_by_id(task_id=task_id)['response']
            end_time = task_status_response['endTime']
        time.sleep(5)

        file_info = task_status_response['progress']

        file_info_json = json.loads(file_info)
        file_id = file_info_json['fileId']
        logging.info(' Commands output file Id: ' + file_id + '\n')

        # retrieve the commands output from file
        logging.info(' Knowledgebase CLI commands output:')
        if hasattr(cc_api.file, "download_a_file_by_file_id"):
            file_content = cc_api.file.download_a_file_by_file_id(file_id=file_id).data
        else:
            file_content = cc_api.file.download_a_file_by_fileid(file_id=file_id).data
        file_content_data = file_content.decode('ASCII')
        file_content_json = json.loads(file_content_data)
        command_responses_success = file_content_json[0]['commandResponses']['SUCCESS']
        command_response_data = 'The device: ' + device_hostname + ' command: ' + command
        for key in command_responses_success:
            command_response_data += '\n    ' + command_responses_success[key]
        logging.info(command_response_data)

        # save to command runner output data to DATASET folder
        with open(APPS_PATH + '/DATASET/' + device_hostname + '_' + issue_name + '_' + command.replace(' ', '-'), 'w') as f:
            f.write(command_response_data)

    logging.info(' Knowledgebase commands execution completed')

    current_time = str(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    logging.info(' App "Network Troubleshooting.py" run end, ' + current_time)


if __name__ == '__main__':
    main()
