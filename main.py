from core.database import Database
from core.scanner import Scanner

from config.settings import VERSION


print("="*60)
print(f"Archivista IA v{VERSION}")
print("="*60)


db = Database()


scanner = Scanner(db)


scanner.scan()


db.close()


print()
print("Proceso terminado.")