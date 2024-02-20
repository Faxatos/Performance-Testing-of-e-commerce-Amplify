import os
import requests
import boto3
import json
import random
import time
import numpy as np
import sys
import matplotlib.pyplot as plt

from datetime import datetime
from threading import Thread
from threading import Event
from dotenv import load_dotenv
from aws_requests_auth.aws_auth import AWSRequestsAuth
load_dotenv() # Load environment variables from the .env file

username_shard = 'FaxyBuyer'
password_shard = 'FaxyBuyer'

mu = 10 # Variables related to Gaussian curve value generation
sigma = 3

conversion_rate = 0.0271 # Conversion rate
avg_session_time = 38 # Random value will be added
accounts_number = 5 # Number of accounts used

# Authorizations for each API to be used (to directly call APIs,
# it's necessary to authenticate through the IAM identity used to create them)
authProd = AWSRequestsAuth(aws_access_key=os.getenv('ACCESS_KEY'),
                       aws_secret_access_key=os.getenv('SECRET_ACCESS_KEY'),
                       aws_host=os.getenv('PRODUCTS_HOST'),
                       aws_region=os.getenv('REGION_NAME'),
                       aws_service='execute-api')
                       
authCart = AWSRequestsAuth(aws_access_key=os.getenv('ACCESS_KEY'),
                       aws_secret_access_key=os.getenv('SECRET_ACCESS_KEY'),
                       aws_host=os.getenv('CARTS_HOST'),
                       aws_region=os.getenv('REGION_NAME'),
                       aws_service='execute-api')
                       
authOrder = AWSRequestsAuth(aws_access_key=os.getenv('ACCESS_KEY'),
                       aws_secret_access_key=os.getenv('SECRET_ACCESS_KEY'),
                       aws_host=os.getenv('ORDERS_HOST'),
                       aws_region=os.getenv('REGION_NAME'),
                       aws_service='execute-api')

client = boto3.client('cognito-idp', region_name=os.getenv('REGION_NAME'))

# Function to check if a number is float
def isfloat(num): 
    try:
        float(num)
        return True
    except ValueError:
        return False

# Function to generate plots
def generatePlots(results, test_len, virtual_users, CV_multiplier):
    # Variables to contain error sums
    prod_errors_sum = 0
    cart_errors_sum = 0
    order_errors_sum = 0
    # Arrays to contain call averages
    product_time_elapsed = np.array([])
    cart_time_elapsed = np.array([])
    order_time_elapsed = np.array([])
    # Arrays to contain success counts per call
    product_succs = np.array([])
    cart_succs = np.array([])
    order_succs = np.array([])
    
    # Iterate through all elements obtained from the Threads, and decompose the results into previously declared variables
    for i in range(len(results)):
        product_time_elapsed = np.append(product_time_elapsed, results[i]['product/get']['avg_time_elapsed'])
        product_succs = np.append(product_succs, results[i]['product/get']['succs'])
        prod_errors_sum += results[i]['product/get']['errors']
        if 'cart/put' in results[i]:
            cart_time_elapsed = np.append(cart_time_elapsed, results[i]['cart/put']['avg_time_elapsed'])
            cart_succs = np.append(cart_succs, results[i]['cart/put']['succs'])
            cart_errors_sum += results[i]['cart/put']['errors']
            
            order_time_elapsed = np.append(order_time_elapsed, results[i]['order/post']['avg_time_elapsed'])
            order_succs = np.append(order_succs, results[i]['order/post']['succs'])
            order_errors_sum += results[i]['order/post']['errors']
    
    # Calculate the sum of successful calls
    prod_succs_sum = np.sum(product_succs)
    cart_succs_sum = np.sum(cart_succs)
    order_succs_sum = np.sum(order_succs)
    
    # Calculate the weighted average based on the number of successful calls
    if prod_succs_sum != 0:
        product_time_elapsed_avg = int(np.average(product_time_elapsed,weights = product_succs))
    else:
        product_time_elapsed_avg = 0
    if cart_succs_sum != 0:
        cart_time_elapsed_avg = int(np.average(cart_time_elapsed,weights = cart_succs))
    else :
        cart_time_elapsed_avg = int(np.average(cart_time_elapsed,weights = cart_succs))
    if order_succs_sum != 0:
        order_time_elapsed_avg = int(np.average(order_time_elapsed,weights = order_succs))
    else:
        order_time_elapsed_avg = 0
    
    # Code for constructing the graphical representation of the first plot (shows average time in ms for calls to various APIs)
    keys = np.flip(np.array(list(results[0].keys())))
    vals = [order_time_elapsed_avg, cart_time_elapsed_avg, product_time_elapsed_avg]
    
    now = datetime.now()
    
    plt.rcParams.update({'font.size': 18})
    
    fig, ax = plt.subplots()
    fig.set_size_inches(15, 5)
    
    bars = ax.barh(keys, vals, color='#1a53ff', height=0.5)
    
    plt.xticks([])
    
    vals_ms = []

    for c in ax.containers:
        vals_ms = [(str(v) + "ms") if v > 0 else "" for v in c.datavalues]
    
    ax.bar_label(bars, labels=vals_ms, padding = -70, color='white', fontweight='bold', fontsize = 14)
    
    plt.xlabel('Average time in ms', fontsize = 16)
    
    plt.title("[Test duration: " + test_len + "s / Concurrently connected users: " + str(int(virtual_users)*accounts_number) + " / Conversion rate multiplier: " + CV_multiplier + "]", fontsize=15)
    plt.suptitle("Average wait time for each API call", fontsize=20, y=1)
    
    # Save the plot if there is a "plots" folder
    if os.path.isdir("plots"):
        plt.savefig("plots/API-ACHT-"+now.strftime("%d-%m-%Y-%H:%M:%S")) #TCM = Average Call Handling Time per [num] Users
    
    plt.show() # Show the first created plot
    
    # Code for constructing the graphical representation of the second plot (shows number of successes/failures of calls to various APIs)
    succs_sum = [order_succs_sum, cart_succs_sum ,prod_succs_sum]
    errors_sum = [order_errors_sum, cart_errors_sum ,prod_errors_sum]
    
    fig, ax = plt.subplots()
    fig.set_size_inches(15, 5)
    
    errors = ax.barh(keys, errors_sum, color='#b30000', height=0.5)
    calls = ax.barh(keys, succs_sum, left=errors_sum ,color='#5ad45a', height=0.5)
    
    plt.xticks([])
    
    ax.bar_label(calls, padding = -45, color='black', fontweight='bold', fontsize = 14)

    n = 0
    for c in ax.containers:
        if n == 0:
            labels = [v if v > 0 else "" for v in c.datavalues]    
            ax.bar_label(c, labels=labels, padding = -45, color='white', fontweight='bold', fontsize = 14)
            n = 1
        else:
            n = 0
    
    plt.xlabel('Number of calls',fontsize = 16)
    
    plt.title("[Test duration: " + test_len + "s / Concurrently connected users: " + str(int(virtual_users)*accounts_number) + " / Conversion rate multiplier: " + CV_multiplier + "]", fontsize=15)
    plt.suptitle("Total number of calls made to APIs", fontsize=20, y=1)
    
    # Save the plot if there is a "plots" folder
    if os.path.isdir("plots"):
        plt.savefig("plots/API-TCM-"+now.strftime("%d-%m-%Y-%H:%M:%S")) #TCM = Total Calls Made by [num] Users
        print("plots generated under /plots")
    
    plt.show() # Show the second created plot
    
# Function for the buyer test case    
def buyerTestCase(endEvent, result, index, virtual_users, conversion_rate_multiplier):
    
    time.sleep(avg_session_time/(index+1)) # Sleep used to desynchronize requests
    random.seed(time.time()) # Generate a new seed for random numbers
    
    # Construct username and password to use for login
    username = username_shard + str(index)
    password = username_shard + str(index)
    
    # Arrays to save the times taken by individual calls
    prod_time_elapsed = []
    cart_time_elapsed = []
    order_time_elapsed = []
    # Variables to count the number of successful calls
    prod_succs = 0
    cart_succs = 0
    order_succs = 0
    # Variables to count the number of unsuccessful calls
    prod_errors = 0
    cart_errors = 0
    order_errors = 0
    
    #1) Client login using username and password.
    #   The accessToken is included in the response.
    response = client.initiate_auth(
        ClientId=os.getenv('COGNITO_USER_CLIENT_ID'),
        AuthFlow='USER_PASSWORD_AUTH',
        AuthParameters={
            'USERNAME': username,
            'PASSWORD': password
        }
    )
    
    # Loop until the endEvent flag is set (set to True)
    while not(endEvent.is_set()):
        st = time.time()# Start time of the call
        #2) API call to get all products
        productsJSON = requests.get(os.getenv('PRODUCTS_API_ENDPOINT'), auth=authProd)
        et = time.time() # End time of the call
        
        if productsJSON.status_code != 200: # In case of error
            prod_errors += 1 # Count the error
            continue         # And reset the buyer case
        # If successful, save the time/success of the call and process the response contents
        prod_time_elapsed.append(int((et - st) * 1000))
        prod_succs += 1
        products = json.loads(productsJSON.content)
        
        # Generate wait time related to the session duration
        session_length = avg_session_time + random.gauss(mu, sigma)
        time.sleep(session_length/virtual_users) # Wait for the session length
        
        gen = random.random() # Generate random number
        
        if gen >= conversion_rate * conversion_rate_multiplier: # Conversion rate
            #2.5) If the generated number is not within the conversion rate, then simulate a new user
            continue
            
        #3) Choose a random product if the generated number is within the conversion rate
        chosenProd = random.choice(products)
        
        # Prepare headers and payload for the cart API call
        headers = {'Accept': "application/json, text/plain, */*", 'content-type': "application/json; charset=UTF-8"}
        payload = {'buyerUsername':username.lower(), 'addedTimestamp': int(time.time() * 1000), 'sellerUsername':chosenProd["sellerUsername"], 'productName':chosenProd["productName"], 'quantity':'1'}
        st = time.time()
        #4) API call to insert the randomly selected product into the cart
        cartResponse = requests.put(os.getenv('CARTS_API_ENDPOINT'), data=json.dumps(payload), headers=headers, auth=authCart)
        et = time.time()
        
        if cartResponse.status_code != 200: # In case of error
            cart_errors += 1                # Count the error
            continue                        # And reset the buyer case
        # If successful, save the call data
        cart_time_elapsed.append(int((et - st) * 1000))
        cart_succs += 1
        
        # Prepare headers and payload for the order API call
        query = {'accessToken':response['AuthenticationResult']['AccessToken']}
        payload = {'buyerUsername':username.lower(), 'status': 'drafted', 'sellerUsername':chosenProd["sellerUsername"], 'productName':chosenProd["productName"], 'quantity':'1'}
        st = time.time()
         #5) API call to generate the order
        orderResponse = requests.post(os.getenv('ORDERS_API_ENDPOINT'), params=query, headers=headers, data=json.dumps(payload), auth=authOrder)
        et = time.time()
        #print("order call: " + str(int((et - st) * 1000)))  #DEBUG
        
        if orderResponse.status_code != 200: # In case of error
            order_errors += 1 # Count the error
        else:
            # If successful, save the call data
            order_time_elapsed.append(int((et - st) * 1000))
            order_succs += 1
    
    # Once the simulation is finished, logout is performed
    res = client.global_sign_out(
        AccessToken=response['AuthenticationResult']['AccessToken']
    )
        
     # The results are saved in the dictionary (only if there is at least one call to the APIs)
    result_resp = {}
    if prod_succs!= 0 or prod_errors!=0:
        if prod_succs != 0:
            result_resp.update({"product/get": {
                "avg_time_elapsed":int(np.array(prod_time_elapsed).mean()), "succs":prod_succs, "errors":prod_errors
            }})
        else:
            result_resp.update({"product/get": {
                "avg_time_elapsed":0, "succs":prod_succs, "errors":prod_errors
            }})
    if cart_succs!= 0 or cart_errors!=0:
        if cart_succs != 0:
            result_resp.update({"cart/put": {
            "avg_time_elapsed":int(np.array(cart_time_elapsed).mean()), "succs":cart_succs, "errors":cart_errors
        }})
        else:
            result_resp.update({"cart/put": {
            "avg_time_elapsed":0, "succs":cart_succs, "errors":cart_errors
        }})
    if order_succs!= 0 or order_errors!=0:
        if order_succs != 0:
            result_resp.update({"order/post": {
            "avg_time_elapsed":int(np.array(order_time_elapsed).mean()), "succs":order_succs, "errors":order_errors
        }})
        else:
            result_resp.update({"order/post": {
            "avg_time_elapsed":0, "succs":order_succs, "errors":order_errors
        }})
    
    # Finally, the data related to the calls are placed in the shared memory area between process and Threads
    result[index] = result_resp

def main():
    # sys.argv[1] -> test length / sys.argv[2] = virtual users per account / sys.argv[3] = conversion rate multiplier
    # Check command line parameter properties
    if len(sys.argv) == 4:
        if (sys.argv[1].isdigit() and sys.argv[2].isdigit() and isfloat(sys.argv[3]) and int(sys.argv[1]) >= 600 and int(sys.argv[2]) >= 1 and float(sys.argv[3]) >= 0):
            
            threads = [None] * accounts_number # Array of threads
            results = [None] * accounts_number # Shared memory where threads will save results
            
            endEvent = Event() # Mechanism used for communication between process and Threads. Boolean flag initialized to False
             
            for i in range(0, accounts_number): # Generate a Thread for each account
                threads[i] = Thread(target=buyerTestCase, args=(endEvent, results, i, int(sys.argv[2]), float(sys.argv[3]))) # Each Thread is passed the function to simulate the use case along with its arguments
                threads[i].start() # Then started
            
            for i in range(1, 11):
                time.sleep(int(sys.argv[1])/10) # At every 10% of the test
                print("completion percentage: " + str(i) + "0%") # The user is notified
                
            endEvent.set() # Boolean flag set to True to terminate the generated Threads
                
            for i in range(accounts_number):
                threads[i].join() # Wait for the Threads to finish
                print(results[i])
                
            generatePlots(results, sys.argv[1], sys.argv[2], sys.argv[3]) # Finally, generate the histograms 
        else: # Error message
            print("[test length in seconds] must be a positive integer > 600 / [virtual users per account] must be a positive integer > 1 / [conversion rate multiplier] must be a float >= 0")
    else: # Error message
        print("parameters error / usage: " + sys.argv[0] + " [test length in seconds] [virtual users per account] [conversion rate multiplier]")
        
    
    
if __name__ == "__main__":
    main()