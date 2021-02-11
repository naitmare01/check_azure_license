#!/usr/bin/python
from __future__ import print_function
from __future__ import division
import argparse
import requests
import urllib3
# urllib3 is only needed to supress insecure https connection.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

OK = 0
WARNING = 1
CRITICAL = 2
UNKNOWN = 3
API_TIMEOUT = 10


def arguments():

    # Handle command line arguments
    parser = argparse.ArgumentParser(description='Monitoring Azure Licenses.')
    parser.add_argument('-u', '--url', help="Base-URL Microsoft login. E.g. 'https://login.microsoftonline.com'.", required=True)
    parser.add_argument('-g', '--graphurl', help="Base-URL Microsoft graph api. E.g. 'https://graph.microsoft.com/v1.0/subscribedSkus'.", required=True)
    parser.add_argument('-t', '--tenantid', help="Tenant ID to Azure in GUID-format.", required=True)
    parser.add_argument('-C', '--clientid', help="Client ID to Azure App in GUID-format.", required=True)
    parser.add_argument('-P', '--clientsecret', help="Client Secret to Azure App.", required=True)
    parser.add_argument('-s', '--skupartnumber', help="skuPartNumber to Azure license e.g. 'VISIOCLIENT'.", type=str.upper, required=True)
    parser.add_argument('-p', '--percent', help='Indicates if calculation should be made in percent. Default is numeric.', action='store_true')
    parser.add_argument('-a', '--all', help='Indicates if all avalible licenses should be checked. Can only check against percentage.', action='store_true')
    parser.add_argument('-w', '--warning', help='Int, warning', type=int, required=True)
    parser.add_argument('-c', '--critical', help='Int, critical', type=int, required=True)

    args = parser.parse_args()

    if args.all and args.percent is False:
        parser.error("--all requires --percentage.")

    return args


def login(url, client_id, client_secret):

    headers = {
        'Content-Type': 'application/x-www-form-urlencoded'
    }

    payload = 'client_id=' + client_id + '&scope=https%3A//graph.microsoft.com/.default&client_secret=' + client_secret + '&grant_type=client_credentials'

    try:
        response = requests.request("POST", url, headers=headers, data=payload, verify=False, timeout=API_TIMEOUT)
    except requests.exceptions.RequestException as error_msg:
        print(error_msg)
        exitcode = WARNING
        exit(exitcode)

    return response


def get_all_skus(graph_url, token, warning, critical):

    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + token
    }

    try:
        response = requests.request("GET", graph_url, headers=headers, verify=False, timeout=API_TIMEOUT)
    except requests.exceptions.RequestException as error_msg:
        print(error_msg)
        exitcode = WARNING
        exit(exitcode)

    nodes = response.json()["value"]
    result = ""
    perf_data = ""
    sku_pct = {}

    for unit in nodes:
        if unit["capabilityStatus"] == "Enabled":
            product = unit["skuPartNumber"]
            consumed_units = unit["consumedUnits"]
            prepaid_units = unit["prepaidUnits"]["enabled"]
            percent_taken = int((consumed_units / prepaid_units) * 100)
            sku_pct[product] = percent_taken

    for key, val in sku_pct.items():
        perf_data = perf_data + " '" + key + "'=" + str(val) + "%;"
    perf_data = perf_data.rstrip().rstrip(';')

    if all((warning > i < critical) for i in sku_pct.values()):
        result = "LICENSE USAGE OK"
        exitcode = OK
    elif any((warning <= i < critical) for i in sku_pct.values()):
        newresult = dict((filter(lambda elem: (warning <= elem[1] < critical), sku_pct.items())))
        for key, val in newresult.items():
            result = result + key + ": " + str(val) + "%, "
        result = "LICENSE USAGE WARNING: " + result
        exitcode = WARNING
    elif any(i >= critical for i in sku_pct.values()):
        newresult = dict((filter(lambda elem: elem[1] >= critical, sku_pct.items())))
        for key, val in newresult.items():
            result = result + key + ": " + str(val) + "%, "
        result = "LICENSE USAGE CRITICAL: " + result
        exitcode = CRITICAL
    else:
        result = "LICENSE USAGE UNKNOWN"
        exitcode = UNKNOWN

    result = result.rstrip().rstrip(',')  # Remove trailing comma and whitespace
    result = result + " |" + perf_data

    print(result)
    exit(exitcode)


def get_skupartnumber_status(graph_url, token, skupart, warning, critical, percent):

    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + token
    }

    try:
        response = requests.request("GET", graph_url, headers=headers, verify=False, timeout=API_TIMEOUT)
    except requests.exceptions.RequestException as error_msg:
        print(error_msg)
        exitcode = WARNING
        exit(exitcode)

    nodes = response.json()["value"]
    result = ""
    perf_data = ""

    for unit in nodes:
        product = unit["skuPartNumber"]
        if product == skupart:
            consumed_units = unit["consumedUnits"]
            prepaid_units = unit["prepaidUnits"]["enabled"]
            percent_taken = int((consumed_units / prepaid_units) * 100)
            units_left = prepaid_units - consumed_units
            perf_data = " | consumed_units=" + str(consumed_units) + "; prepaid_units=" + str(prepaid_units) + "; percent_taken=" + str(percent_taken) + "; units_left=" + str(units_left)

            if consumed_units == prepaid_units:
                result = "LICENSE USAGE CRITICAL for " + product + ": " + str(consumed_units) + " of " + str(prepaid_units) + " taken."
                exitcode = CRITICAL

            if percent:
                if (warning > percent_taken < critical):
                    result = "LICENSE USAGE OK for " + product + ": " + str(percent_taken) + "% used."
                    exitcode = OK
                elif (warning <= percent_taken < critical):
                    result = "LICENSE USAGE WARNING for " + product + ": " + str(percent_taken) + "% used."
                    exitcode = WARNING
                elif percent_taken >= critical:
                    result = "LICENSE USAGE CRITICAL for " + product + ": " + str(percent_taken) + "% used."
                    exitcode = CRITICAL
                else:
                    result = "LICENSE USAGE UNKNOWN for " + product
                    exitcode = CRITICAL
            else:
                if (warning > units_left < critical):
                    result = "LICENSE USAGE OK for " + product + ": " + str(units_left) + " left."
                    exitcode = OK
                elif (warning <= units_left < critical):
                    result = "LICENSE USAGE WARNING for " + product + ": " + str(units_left) + " left."
                    exitcode = WARNING
                elif units_left >= critical:
                    result = "LICENSE USAGE CRITICAL for " + product + ": " + str(units_left) + " left."
                    exitcode = CRITICAL
                else:
                    result = "LICENSE USAGE UNKNOWN for " + product
                    exitcode = CRITICAL
            break
        else:
            result = "Product " + skupart + " not found in tenant."
            exitcode = UNKNOWN
    result = result + perf_data

    print(result)
    exit(exitcode)


def main():
    args = arguments()
    apiurl = args.url.strip("/")  # Remove trailing slash from URL.
    graph_url = args.graphurl.strip("/")  # Remove trailing slash from URL.

    if not apiurl.startswith("https://"):
        apiurl = apiurl.replace("http://", "")
        apiurl = "https://" + apiurl

    if not graph_url.startswith("https://"):
        graph_url = graph_url.replace("http://", "")
        graph_url = "https://" + graph_url

    args.graphurl = graph_url
    args.url = apiurl + "/" + args.tenantid + "/oauth2/v2.0/token"
    apilogin = login(args.url, args.clientid, args.clientsecret)

    if apilogin.status_code == 200:
        apitoken = apilogin.json()['access_token']
        args.apitoken = apitoken
        if args.all:
            get_all_skus(args.graphurl, args.apitoken, args.warning, args.critical)
        else:
            get_skupartnumber_status(args.graphurl, args.apitoken, args.skupartnumber, args.warning, args.critical, args.percent)
    else:
        print("CRITICAL: Unable to login")
        exitcode = CRITICAL
        exit(exitcode)


if __name__ == '__main__':
    main()
