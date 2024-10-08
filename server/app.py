from flask import Flask, request, jsonify, send_from_directory
import firebase_admin
from firebase_admin import credentials, messaging
from dotenv import load_dotenv
import os
from flask_sqlalchemy import SQLAlchemy
#from flask_cors import CORS


load_dotenv()  # Load environment variables from .env file

app = Flask(__name__, static_folder='build', static_url_path='')
#CORS(app, origins=['http://localhost:3002'])


#build
@app.route('/')
def serve():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory(app.static_folder, path)

@app.route('/api/example', methods=['GET'])
def example():
    return jsonify(message="Hello from Flask!")









from supabase import create_client, Client

# Supabase configuration
SUPABASE_URL = os.environ['SUPABASE_URL']
SUPABASE_KEY = os.environ['SUPABASE_KEY']
SUPABASE_SECRET = os.environ['SUPABASE_SECRET']

options = {
    "headers": {
        "Authorization": f"Bearer {SUPABASE_KEY}"
    }
}

supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)



@app.route('/test_supabase', methods=['GET'])
def test_supabase():
    try:
        response = supabase_client.table('users').select('*').limit(1).execute()
        return jsonify({'message': 'Supabase connection successful', 'data': response.data})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/store_user', methods=['POST'])
def store_user():
    data = request.json
    name = data['name']
    location = data['location']
    email = data['email']
    #token = data['token']

    # Create a new user in the Supabase table
    user = supabase_client.table('fcm_users').insert({
        'username': name,
        'email': email,
        'location': location,
        'authority' : 'admin',
        #'token': {'fcm_token': token},
    }).execute()

    return jsonify({'message': 'User created successfully'})

@app.route('/store_token', methods=['POST'])
def store_token():
    try:
        data = request.json
        user_email = data['email']
        token = data['token']

        # Fetch the user ID from the Supabase table
        user = supabase_client.table('fcm_users').select('id', 'token').eq('email', user_email).execute()
        
        if not user.data:
            return jsonify({'error': 'User not found'}), 404
        
        user_id = user.data[0]['id']
        existing_token = user.data[0].get('token')

        if existing_token and existing_token.get('fcm_token') == token:
            return jsonify({'message': 'Token stored successfully', 'token': token})

        # Update the user token in the Supabase table
        supabase_client.table('fcm_users').update({
            'token': {'fcm_token': token}
        }).eq('id', user_id).execute()

        return jsonify({'message': 'Token stored successfully', 'token': token})
    except Exception as e:
        app.logger.error(f"Error in store_token: {str(e)}")
        return jsonify({'error': str(e)}), 500
    
#send fcm code

cred = credentials.Certificate(os.environ['GOOGLE_APPLICATION_CREDENTIALS'])
firebase_admin.initialize_app(cred)

@app.route('/send_web_push', methods=['POST'])
def send_web_push_notification():
    try:
        # Retrieve all user tokens from the Supabase database
        users = supabase_client.table('fcm_users').select('token').execute()
        
        # Filter out any users without valid tokens
        tokens = [user['token']['fcm_token'] for user in users.data if user.get('token') and user['token'].get('fcm_token')]
        
        if not tokens:
            return jsonify({'message': 'No valid tokens found'}), 400

        # Create a notification message
        message = messaging.MulticastMessage(
            notification=messaging.Notification(
                title='Car Accident Alert!',
                body='Be careful! There has been a car accident near your locality. Click to know more at https://localhost:5000/incidents/latest'
            ),
            tokens=tokens
        )

        # Send the message
        response = messaging.send_multicast(message)
        
        # Log the response
        app.logger.info(f'Successfully sent message: {response}')
        
        # Provide more detailed response
        return jsonify({
            'message': 'Web push notification sent successfully',
            'success_count': response.success_count,
            'failure_count': response.failure_count,
            'notification': {
                'title': 'Car Accident Alert!',
                'body': 'Be careful! There has been a car accident near your locality.'
            }
        })

    except Exception as e:
        app.logger.error(f"Error in send_web_push: {str(e)}")
        return jsonify({'error': str(e)}), 500


## INCIDENTS
@app.route('/incidents', methods=['POST'])
def create_incident():
    try:
        data = request.json
        incident_type = data['incident_type']
        image_url = data.get('image_url')  # Optional field

        new_incident = supabase_client.table('incidents').insert({
            'incident_type': incident_type,
            'image_url': image_url
        }).execute()

        return jsonify(new_incident.data[0]), 201
    except Exception as e:
        app.logger.error(f"Error in create_incident: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/incidents', methods=['GET'])
def get_all_incidents():
    try:
        incidents = supabase_client.table('incidents').select('*').order('time_of_incident', desc=True).execute()
        return jsonify(incidents.data)
    except Exception as e:
        app.logger.error(f"Error in get_all_incidents: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/incidents/latest', methods=['GET'])
def get_latest_incident():
    
    try:
        latest_incident = supabase_client.table('incidents').select('*').order('time_of_incident', desc=True).limit(1).execute()
        if latest_incident.data:
            incident_data = latest_incident.data[0]
            incident_type = incident_data['incident_type']
            time_of_incident = incident_data['time_of_incident']
            image_url = incident_data.get('image_url')

            response = {
                'message': f'Car Accident Alert!',
                'details': f'A car accident occurred at {time_of_incident}. Please be cautious while driving.',
                'image_url': image_url,
                'incident_type': incident_type
            }
            return jsonify(response)
        else:
            return jsonify({'message': 'No incidents found'}), 404
    except Exception as e:
        app.logger.error(f"Error in get_latest_incident: {str(e)}")
        return jsonify({'error': str(e)}), 500

## MODEL


if __name__ == '__main__':
    app.run(debug=True)