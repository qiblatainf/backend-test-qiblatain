from flask import jsonify

class DataframeCreationError(Exception):
    ''' custom exception class '''
    pass

def handle_dataframe_error(error):
    response = jsonify({"Error": str(error)})
    response.status_code = 500  # Internal Server Error
    return response
