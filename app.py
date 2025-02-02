from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import create_engine
from dataclasses import dataclass
from exceptions import DataframeCreationError
import pandas as pd

from flask import Flask
app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///testdata.db'
db = SQLAlchemy(app)


#### SPACE FOR DATABASE STUFF ####

@dataclass
class AppLog(db.Model):
    __tablename__ = 'applog'
    # TODO
    id: int = db.Column(db.BigInteger, primary_key=True)
    timestarted: str = db.Column(db.DateTime, nullable=False)
    timeended: str = db.Column(db.DateTime, nullable=True)
    userid: str = db.Column(db.Text, nullable=False)
    applicationname: str = db.Column(db.Text, nullable=False)
    windowtitle: str = db.Column(db.Text, nullable=True)

@dataclass
class UILog(db.Model):
    __tablename__ = 'uilog'
    # TODO
    id: int = db.Column(db.BigInteger, primary_key=True)
    userid: str = db.Column(db.Text, nullable=False)
    appid: int = db.Column(db.BigInteger, db.ForeignKey('applog.id'), nullable=False) #belongs to AppLog class
    eventtype: str = db.Column(db.Text, nullable=False)
    name: str = db.Column(db.Text, nullable=True)
    acceleratorkey: str = db.Column(db.Text, nullable=True)
    timestamp: str = db.Column(db.DateTime, nullable=False)

    #AppLog is the Parent, UILog is the Child (1:n relationship), 1 app has many ui logs
    # app = db.relationship("AppLog", foreign_keys=[appid], primaryjoin="and_(uilog.appid == applog.id, uilog.userid == applog.userid)")

'''
sqlite> .schema applog
CREATE TABLE applog (
        id BIGINT,
        timestarted DATETIME,
        timeended DATETIME,
        userid TEXT,
        applicationname TEXT,
        windowtitle TEXT
);
sqlite> .schema uilog
CREATE TABLE uilog (
        id BIGINT,
        userid TEXT,
        appid BIGINT,
        eventtype TEXT,
        name TEXT,
        acceleratorkey TEXT,
        timestamp DATETIME
);
'''

'''Result model'''
@dataclass
class CopyPasteResult:
    fromApp : str
    toApp : str
    count: int

#### SPACE FOR API ENDPOINTS ####


@app.route('/')
def index():
    return {"message": "Hello, World!"}

@app.route('/copyPasteAnalysis')
def copyPasteAnalysis():
    # TODO
    data = createDataframe()
    copiedEvents, pastedEvents = filterCopyPasteEvents(data)
    copyPasteAnalysis = analysis(copiedEvents, pastedEvents)

    results = [
        CopyPasteResult(fromApp=row[0], toApp=row[1], count=row[2])
        for row in copyPasteAnalysis.itertuples(index=False)
    ]

    return results
    
def createDataframe():
    '''This function connects to database, 
    converts sql data to dataframe and merge them into one
    '''
    engine = create_engine(app.config['SQLALCHEMY_DATABASE_URI'])
    try:
        with engine.connect() as connection:
            appLogDf = pd.read_sql(AppLog.__table__.select(), connection)
            uiLogDf = pd.read_sql(UILog.__table__.select(), connection)

            '''ALTERNATE method - using sql query
            loading data into dataframe (we will only read the columns we need)
            appLogDf = pd.read_sql("SELECT id, userid, applicationname FROM applog", connection)
            uiLogDf = pd.read_sql("SELECT id, userid, appid, eventtype, acceleratorkey, timestamp FROM uilog", connection) 
            '''

            #null check
            if appLogDf is None or appLogDf.empty:
                raise DataframeCreationError("No data found in the 'applog' table.")
            if uiLogDf is None or uiLogDf.empty:
                raise DataframeCreationError("No data found in the 'uilog' table.")

        #creating one data frame by performing join
        data = uiLogDf.merge(appLogDf, left_on=['appid', 'userid'], right_on=['id', 'userid'], suffixes=('ui', 'app'))
        data.drop(columns=['appid'], inplace=True) #remove duplicate appid column
        data['timestamp'] = pd.to_datetime(data['timestamp']) #type casting from string to dattetime format

        return data
    
    except Exception as e:
        raise DataframeCreationError(f"Database connection failed: {e}")

def filterCopyPasteEvents(data):
    '''This function filters copy and paste events. 
       A new column called 'actioncategory' is added to define if the event refers to a 'copy' event or 'paste' event
    '''

    #identify events where the data was copied/clicked "FROM"
    ctrlEvent = data[(data['eventtype'].isin(['CTRL + C', 'CTRL + X']))]
    clickedEvent = data[((data['eventtype'] == 'Left-Down') & (data['acceleratorkey'] == 'STRG+C'))]
    copiedEvents = pd.concat([ctrlEvent, clickedEvent], ignore_index=True)    
    copiedEvents["actioncategory"] = "copy"
    copiedEvents = copiedEvents[['userid', 'applicationname', 'timestamp', 'eventtype', 'acceleratorkey', 'actioncategory']]
    
    #identify events where the data was copied/clicked "TO"
    pastedEvents = data[data['eventtype'] == 'CTRL + V']
    pastedEvents["actioncategory"] = "paste"
    pastedEvents = pastedEvents[['userid', 'applicationname', 'timestamp', 'eventtype', 'acceleratorkey', 'actioncategory']]

    return copiedEvents, pastedEvents

def analysis(copiedEvents, pastedEvents):
    '''This function performs analysis by merging the copy events and paste event. 
    It's followed by sorting the merged data in the order of userid and then timestampe.
    We then creating a 'next action category' column which refers to the category of the next record 
    (to check if a paste action was followed by a copy action AND to check the next application the action
    was performed on). 
    And finally the aggregation is performed.

    CASE 1 : copied from app1 to app1 - does not count
    CASE 2 : copied from app1 to app2 n times - counts as 1
    CASE 3 : copied from app1 to no app - does not count i.e. keeping events where a copy is followed by a paste, if no paste in the next action, then we don't include it
    '''
  
    copyPasteAnalysis = pd.concat([copiedEvents, pastedEvents]) #concatenate the copy and paste events into one
    copyPasteAnalysis = copyPasteAnalysis.sort_values(['userid', 'timestamp']) #order by userid first and then timestamp   

    copyPasteAnalysis['nextactioncategory'] = copyPasteAnalysis.groupby('userid')['actioncategory'].shift(-1) #adding the next action i.e. is it copy or paste    
    copyPasteAnalysis['nextapplicationname'] = copyPasteAnalysis.groupby('userid')['applicationname'].shift(-1) #check which application is the next action performed on

    copyPasteAnalysis = copyPasteAnalysis[(copyPasteAnalysis['actioncategory'] == 'copy') & (copyPasteAnalysis['nextactioncategory'] == 'paste')].copy() #CASE 3
    
    #the applications within which the action was performed (FROM - TO)
    copyPasteAnalysis['from'] = copyPasteAnalysis['applicationname']
    copyPasteAnalysis['to'] = copyPasteAnalysis['nextapplicationname']
    
    copyPasteAnalysis = copyPasteAnalysis[copyPasteAnalysis['from'] != copyPasteAnalysis['to']] #CASE 1 and 2    
    copyPasteAnalysis = copyPasteAnalysis.groupby(['from', 'to']).size().reset_index(name='count') #aggregating the count
    return copyPasteAnalysis

#testing api
# @app.route("/GetAppLogs")
# def getApplogs():    
#     engine = create_engine(app.config['SQLALCHEMY_DATABASE_URI'])

#     with engine.connect() as connection:
#         sql_query = pd.read_sql("""SELECT * FROM applog""", connection)
#         data = sql_query.to_dict(orient='records')

#     return jsonify(data)
        
    
if __name__ == "__main__":
    # try:
    #     engine = create_engine(app.config['SQLALCHEMY_DATABASE_URI'])
    #     with engine.connect() as connection:
    #         print("Database connection successful!")
    # except Exception as e:
    #     print(f"Database connection failed: {e}")
    app.run(debug=True)

