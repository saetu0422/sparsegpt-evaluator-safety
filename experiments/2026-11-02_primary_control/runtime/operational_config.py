"""Private operator-supplied constraints; never evidence of account authorization."""
from dataclasses import dataclass
from pathlib import Path
import datetime as dt,math

@dataclass(frozen=True)
class OperationalConfig:
 folder_id:str
 owner_account:str
 expected_parent:str
 drive_mount:str
 ephemeral_root:str
 original_connection_utc:str
 last_launch_utc:str
 hard_stop_utc:str
 baseline_cu:float
 stop_balance_cu:float

 def validate(self):
  if not all(isinstance(x,str) and x.strip() for x in (self.folder_id,self.owner_account,self.expected_parent,self.drive_mount,self.ephemeral_root)):raise ValueError('Explicit destination identity and paths required')
  parent,mount,scratch=map(Path,(self.expected_parent,self.drive_mount,self.ephemeral_root))
  if not all(p.is_absolute() for p in (parent,mount,scratch)) or not parent.is_relative_to(mount) or parent==mount or scratch.is_relative_to(mount):raise ValueError('Invalid private path boundaries')
  dates=[dt.datetime.fromisoformat(x) for x in (self.original_connection_utc,self.last_launch_utc,self.hard_stop_utc)]
  if any(x.tzinfo is None for x in dates) or not dates[0]<dates[1]<=dates[2] or dates[2]>dates[0]+dt.timedelta(hours=2):raise ValueError('Timezone-aware original connection and maximum two-hour window required')
  if any(type(x) not in (float,int) or not math.isfinite(x) for x in (self.baseline_cu,self.stop_balance_cu)) or not 0<=self.stop_balance_cu<self.baseline_cu:raise ValueError('Explicit finite positive compute reserve required')
