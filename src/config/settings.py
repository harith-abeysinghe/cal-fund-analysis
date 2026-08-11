"""Settings class handling configuration from .env file"""

import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
class Settings:
    """Configuration loaded from environment variables or defaults."""
    
    def __init__(self, env_file: Optional[Path] = None):
        # Load environment variables from .env file if provided
        if env_file:
            load_dotenv(env_file)
        else:
            load_dotenv()
        
        # Application configuration
        self.base_url: str = os.getenv("CAL_BASE_URL", "https://cal.lk/wp-admin/admin-ajax.php")
        self.max_monthly_investment_lkr: int = int(os.getenv("MAX_MONTHLY_INVESTMENT_LKR", "100000"))
        
        # Directory paths
        self.base_dir: Path = Path("D:/Personal/CAL Fund Analysis")
        self.data_dir: Path = self.base_dir / "data"
        self.output_dir: Path = self.base_dir / "output"
        self.cache_dir: Path = self.base_dir / "cache"
        
        # Ensure directories exist
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)