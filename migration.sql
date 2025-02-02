BEGIN TRANSACTION;

-- creating processes table
CREATE TABLE processes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL UNIQUE
);

-- populate processes table
INSERT INTO processes (name) SELECT DISTINCT process FROM processlog;

-- create cases table
CREATE TABLE cases (
  id SMALLINT PRIMARY KEY,
  processId SMALLINT,
  FOREIGN KEY (processId) REFERENCES processes(id)
);

-- inserting into the cases table (bridge table)
INSERT INTO cases (id, processId) SELECT DISTINCT caseid, p.id FROM processlog JOIN processes p ON processlog.process = p.name;

-- creating newprocesslog table
CREATE TABLE newprocesslog (
  id BIGINT PRIMARY KEY,
  activity TEXT NOT NULL,
  caseId SMALLINT,
  timestamp DATETIME NOT NULL,
  FOREIGN KEY (caseId) REFERENCES cases(id)
);

-- migrate data from processlog to newprocesslog
INSERT INTO newprocesslog (activity, caseId, timestamp) SELECT activity, caseid, timestamp FROM processlog;

-- drop old processlog table, commenting it for now to prevent altering existing db table
--DROP TABLE processlog;

COMMIT;
