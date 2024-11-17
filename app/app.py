from flask import Flask, render_template, jsonify
from datetime import datetime
from mocked_process import MockedProcess
import time

app = Flask(__name__)
process = MockedProcess()

MAX_HISTORY = 10  # Limit for historical data

@app.route('/mocked-data')
def get_mocked_data():
    current_time = time.time()

    # Generate new data only if 5 seconds have passed
    if current_time - process.last_update_time >= 5:
        predicted_food = process.generate_predicted_food_orders()
        actual_food = process.generate_simulated_food_orders(predicted_food)
        accuracy = process.calculate_accuracy(predicted_food, actual_food)

        # Update model_accuracy with the latest accuracy value
        process.model_accuracy = accuracy

        # Append new food order data
        process.predicted_food_orders.append(predicted_food)
        process.simulated_food_orders.append(actual_food)

        # Limit the history size
        if len(process.predicted_food_orders) > MAX_HISTORY:
            process.predicted_food_orders.pop(0)
        if len(process.simulated_food_orders) > MAX_HISTORY:
            process.simulated_food_orders.pop(0)

        # Update the ingredient inventory and track how much was restocked
        restocked_ingredients = process.update_inventory(actual_food, predicted_food)
        process.current_week += 1
        process.last_update_time = current_time
    else:
        restocked_ingredients = {}

    # Check for last available values or generate defaults
    predicted_food_orders = process.predicted_food_orders[-1] if process.predicted_food_orders else process.generate_predicted_food_orders()
    simulated_food_orders = process.simulated_food_orders[-1] if process.simulated_food_orders else process.generate_simulated_food_orders(predicted_food_orders)

    # Prepare data to send to frontend
    data = {
        "predicted_food_orders": predicted_food_orders,
        "food_orders_this_week": simulated_food_orders,  # Directly use simulated_food_orders
        "model_accuracy": process.model_accuracy,  # Single accuracy value
        "inventory": process.inventory,
        "restocked_ingredients": restocked_ingredients,  # New data for restocked ingredients
        "current_week": process.current_week,
        "current_time": datetime.now().strftime("%H:%M:%S")
    }

    return jsonify(data)

    # Reset the process attributes to initial values
    process.inventory = {
        "tomato": 50,
        "spaghetti": 50,
        "cheese": 50,
        "basil": 50,
    }
    process.simulated_food_orders = []
    process.predicted_food_orders = []
    process.model_accuracy = 100  # Start with initial accuracy as a single value
    process.current_week = 1
    process.last_update_time = time.time()  # Reset the time for the next update

    # Return the reset data to the frontend
    data = {
        "predicted_food_orders": process.predicted_food_orders[-1] if process.predicted_food_orders else process.generate_predicted_food_orders(),
        "food_orders_this_week": process.simulated_food_orders[-1] if process.simulated_food_orders else process.generate_simulated_food_orders(process.predicted_food_orders[-1]),
        "model_accuracy": process.model_accuracy,
        "inventory": process.inventory,
        "restocked_ingredients": {},  # No restocked ingredients yet
        "current_week": process.current_week,
        "current_time": datetime.now().strftime("%H:%M:%S")
    }

    return jsonify(data)

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
