from backend.app.connectors import greenhouse, lever, ashby, remoteok, remotive, arbeitnow

def fetch_all_jobs(
    custom_greenhouse: list = None, 
    custom_lever: list = None, 
    custom_ashby: list = None
) -> list:
    """Unified entry point to run all job source connectors in the backend."""
    all_jobs = []
    
    all_jobs.extend(greenhouse.fetch_jobs(custom_greenhouse))
    all_jobs.extend(lever.fetch_jobs(custom_lever))
    all_jobs.extend(ashby.fetch_jobs(custom_ashby))
    all_jobs.extend(remoteok.fetch_jobs())
    all_jobs.extend(remotive.fetch_jobs())
    all_jobs.extend(arbeitnow.fetch_jobs())
    
    return all_jobs
