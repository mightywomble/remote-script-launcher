# api.py
# To run this API, first install the required packages:
# pip install "fastapi[all]" uvicorn python-multipart paramiko SQLAlchemy
#
# Then, run the server from your terminal using the Python interpreter directly:
# python api.py

import os
import sys
import uvicorn
import paramiko
from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional


from sqlalchemy import create_engine, Column, Integer, String, Text
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.exc import IntegrityError

# --- FastAPI App Initialization ---
# Define the app object early to ensure it exists, even if other setup fails.
app = FastAPI(
    title="Remote Script Launcher API",
    description="An API to manage hosts, scripts, and pipelines for remote execution.",
    version="1.5.0",
)

# --- Database Setup ---
# This section connects directly to your existing app.db database.
try:
    DATABASE_URL = "sqlite:///app.db"
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base = declarative_base()
except Exception as e:
    print(f"FATAL: An error occurred during database setup: {e}")
    sys.exit(1)

# --- SQLAlchemy Models ---
# These classes define the database table structure.
class Host(Base):
    __tablename__ = 'host'
    id = Column(String, primary_key=True)
    hostname = Column(String, nullable=False)
    port = Column(Integer, nullable=False)
    username = Column(String, nullable=False)

class Script(Base):
    __tablename__ = 'script'
    id = Column(String, primary_key=True)
    path = Column(String, nullable=False)

class Pipeline(Base):
    __tablename__ = 'pipeline'
    id = Column(String, primary_key=True)
    scripts = Column(Text, nullable=False) # Storing script IDs as a comma-separated string

# --- Pydantic Models for API Data Validation ---
class HostModel(BaseModel):
    id: str = Field(..., description="Unique identifier for the host (e.g., 'prod-server-1').")
    hostname: str = Field(..., description="Hostname or IP address of the server.")
    port: int = Field(default=22, description="SSH port.")
    username: str = Field(..., description="Username for SSH login.")
    
    model_config = ConfigDict(from_attributes=True)

class ScriptModel(BaseModel):
    id: str = Field(..., description="Unique identifier for the script (e.g., 'deploy-app').")
    path: str = Field(..., description="The command or path to the script to be executed.")

    model_config = ConfigDict(from_attributes=True)

class PipelineModel(BaseModel):
    id: str = Field(..., description="Unique identifier for the pipeline (e.g., 'full-deploy').")
    scripts: List[str] = Field(..., description="A list of script IDs to be executed in sequence.")

    model_config = ConfigDict(from_attributes=True)

class ScriptExecutionRequest(BaseModel):
    host_id: str
    script_id: str
    password: Optional[str] = None

class PipelineExecutionRequest(BaseModel):
    host_id: str
    pipeline_id: str
    password: Optional[str] = None

# --- Dependencies ---
def get_db():
    """Dependency to get a DB session for each request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

API_SECRET_TOKEN = os.getenv("API_SECRET_TOKEN", "default_secret_token")
security = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Dependency to verify the bearer token."""
    if credentials.scheme != "Bearer" or credentials.credentials != API_SECRET_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid or missing API token.")
    return credentials.credentials

# --- SSH Execution Logic ---
def execute_ssh_command(host: Host, script: Script, password: Optional[str]):
    """Connects to a host and executes a single script command."""
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(host.hostname, port=host.port, username=host.username, password=password, timeout=10)
        
        stdin, stdout, stderr = client.exec_command(script.path)
        output = stdout.read().decode('utf-8')
        error = stderr.read().decode('utf-8')
        
        client.close()
        
        if error:
            # Return error but don't raise exception unless connection fails
            return f"Error executing script: {error}"
        return output
    except Exception as e:
        # Raise exception for connection errors, auth failures, etc.
        raise Exception(f"SSH connection failed: {e}")

# --- API Endpoints ---

@app.get("/", tags=["Status"])
def read_root():
    return {"status": "Remote Script Launcher API is running."}

# --- Host Management ---
@app.post("/hosts", status_code=201, response_model=HostModel, tags=["Hosts"], summary="Add a new host")
def add_host(host: HostModel, db = Depends(get_db), token: str = Depends(get_current_user)):
    new_host = Host(**host.model_dump())
    db.add(new_host)
    try:
        db.commit()
        db.refresh(new_host)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail=f"Host with id '{host.id}' already exists.")
    return new_host

@app.get("/hosts", response_model=List[HostModel], tags=["Hosts"], summary="List all hosts")
def list_hosts(db = Depends(get_db), token: str = Depends(get_current_user)):
    return db.query(Host).all()

@app.delete("/hosts/{host_id}", status_code=200, tags=["Hosts"], summary="Delete a host")
def delete_host(host_id: str, db = Depends(get_db), token: str = Depends(get_current_user)):
    host = db.query(Host).filter(Host.id == host_id).first()
    if not host:
        raise HTTPException(status_code=404, detail=f"Host '{host_id}' not found.")
    db.delete(host)
    db.commit()
    return {"message": f"Host '{host_id}' deleted successfully."}

# --- Script Management ---
@app.post("/scripts", status_code=201, response_model=ScriptModel, tags=["Scripts"], summary="Add a new script")
def add_script(script: ScriptModel, db = Depends(get_db), token: str = Depends(get_current_user)):
    new_script = Script(**script.model_dump())
    db.add(new_script)
    try:
        db.commit()
        db.refresh(new_script)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail=f"Script with id '{script.id}' already exists.")
    return new_script

@app.get("/scripts", response_model=List[ScriptModel], tags=["Scripts"], summary="List all scripts")
def list_scripts(db = Depends(get_db), token: str = Depends(get_current_user)):
    return db.query(Script).all()

@app.delete("/scripts/{script_id}", status_code=200, tags=["Scripts"], summary="Delete a script")
def delete_script(script_id: str, db = Depends(get_db), token: str = Depends(get_current_user)):
    script = db.query(Script).filter(Script.id == script_id).first()
    if not script:
        raise HTTPException(status_code=404, detail=f"Script '{script_id}' not found.")
    db.delete(script)
    db.commit()
    return {"message": f"Script '{script_id}' deleted successfully."}

# --- Pipeline Management ---
@app.post("/pipelines", status_code=201, response_model=PipelineModel, tags=["Pipelines"], summary="Add a new pipeline")
def add_pipeline(pipeline: PipelineModel, db = Depends(get_db), token: str = Depends(get_current_user)):
    scripts_str = ",".join(pipeline.scripts)
    new_pipeline = Pipeline(id=pipeline.id, scripts=scripts_str)
    db.add(new_pipeline)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail=f"Pipeline with id '{pipeline.id}' already exists.")
    return pipeline

@app.get("/pipelines", response_model=List[PipelineModel], tags=["Pipelines"], summary="List all pipelines")
def list_pipelines(db = Depends(get_db), token: str = Depends(get_current_user)):
    pipelines_db = db.query(Pipeline).all()
    result = []
    for p in pipelines_db:
        # Ensure scripts is a string before splitting
        scripts_list = p.scripts.split(',') if p.scripts else []
        result.append(PipelineModel(id=p.id, scripts=scripts_list))
    return result

@app.delete("/pipelines/{pipeline_id}", status_code=200, tags=["Pipelines"], summary="Delete a pipeline")
def delete_pipeline(pipeline_id: str, db = Depends(get_db), token: str = Depends(get_current_user)):
    pipeline = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
    if not pipeline:
        raise HTTPException(status_code=404, detail=f"Pipeline '{pipeline_id}' not. found")
    db.delete(pipeline)
    db.commit()
    return {"message": f"Pipeline '{pipeline_id}' deleted successfully."}

# --- Execution Endpoints ---
@app.post("/run/script", tags=["Execution"], summary="Execute a script on a host")
def run_script(request: ScriptExecutionRequest, db = Depends(get_db), token: str = Depends(get_current_user)):
    host = db.query(Host).filter(Host.id == request.host_id).first()
    if not host:
        raise HTTPException(status_code=404, detail=f"Host '{request.host_id}' not found.")
    
    script = db.query(Script).filter(Script.id == request.script_id).first()
    if not script:
        raise HTTPException(status_code=404, detail=f"Script '{request.script_id}' not found.")
        
    try:
        output = execute_ssh_command(host, script, request.password)
        return {"message": "Script execution finished.", "output": output}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/run/pipeline", tags=["Execution"], summary="Execute a pipeline on a host")
def run_pipeline(request: PipelineExecutionRequest, db = Depends(get_db), token: str = Depends(get_current_user)):
    host = db.query(Host).filter(Host.id == request.host_id).first()
    if not host:
        raise HTTPException(status_code=404, detail=f"Host '{request.host_id}' not found.")

    pipeline = db.query(Pipeline).filter(Pipeline.id == request.pipeline_id).first()
    if not pipeline:
        raise HTTPException(status_code=404, detail=f"Pipeline '{request.pipeline_id}' not found.")

    script_ids = pipeline.scripts.split(',') if pipeline.scripts else []
    pipeline_results = {}

    for script_id in script_ids:
        script = db.query(Script).filter(Script.id == script_id.strip()).first()
        if not script:
            pipeline_results[script_id] = "Error: Script not found in database."
            continue
        
        try:
            output = execute_ssh_command(host, script, request.password)
            pipeline_results[script_id] = {"status": "success", "output": output}
        except Exception as e:
            pipeline_results[script_id] = {"status": "failure", "output": str(e)}
            break 
            
    return {
        "message": f"Pipeline '{request.pipeline_id}' execution finished on host '{request.host_id}'.",
        "results": pipeline_results
    }

# --- Main Execution Block for Debugging ---
if __name__ == "__main__":
    print("Attempting to start uvicorn server directly...")
    # This block allows running the script with 'python api.py'
    # It provides more detailed error messages than the uvicorn command.
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True, log_level="debug")

