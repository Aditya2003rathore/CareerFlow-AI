from connectors import greenhouse, lever, ashby, remoteok, remotive, arbeitnow

def fetch_all_jobs(
    custom_greenhouse: list = None, 
    custom_lever: list = None, 
    custom_ashby: list = None
) -> list:
    """
    Unified entry point to run all job source connectors.
    Aggregates and returns a single list of normalized job dictionaries.
    """
    all_jobs = []
    
    print("Fetching jobs from Greenhouse...")
    all_jobs.extend(greenhouse.fetch_jobs(custom_greenhouse))
    
    print("Fetching jobs from Lever...")
    all_jobs.extend(lever.fetch_jobs(custom_lever))
    
    print("Fetching jobs from Ashby...")
    all_jobs.extend(ashby.fetch_jobs(custom_ashby))
    
    print("Fetching jobs from RemoteOK...")
    all_jobs.extend(remoteok.fetch_jobs())
    
    print("Fetching jobs from Remotive...")
    all_jobs.extend(remotive.fetch_jobs())
    
    print("Fetching jobs from Arbeitnow...")
    all_jobs.extend(arbeitnow.fetch_jobs())
    
    print(f"Sync complete. Unified total: {len(all_jobs)} jobs.")
    return all_jobs
