from pathlib import Path

from tqdm import tqdm

from config.settings import (
    ROOT_FOLDER,
    VIDEO_EXTENSIONS,
    AUDIO_EXTENSIONS,
    IGNORE_FOLDERS,
)


class Scanner:


    def __init__(self, database):

        self.database = database

        self.videos = 0
        self.audios = 0
        self.otros = 0


    def scan(self):

        print()
        print("Escaneando:", ROOT_FOLDER)
        print()

        archivos = list(self.iter_files())

        print(f"Archivos encontrados: {len(archivos)}")
        print()


        for archivo in tqdm(archivos):

            info = self.process_file(archivo)

            if info:

                self.database.insert_file(info)


        print()
        print("Videos:", self.videos)
        print("Audios:", self.audios)
        print("Otros:", self.otros)



    def iter_files(self):

        for path in ROOT_FOLDER.rglob("*"):

            if path.is_file():

                if any(
                    parte in IGNORE_FOLDERS
                    for parte in path.parts
                ):
                    continue

                yield path



    def process_file(self,path):

        extension = path.suffix.lower()


        if extension in VIDEO_EXTENSIONS:

            tipo="VIDEO"
            self.videos += 1


        elif extension in AUDIO_EXTENSIONS:

            tipo="AUDIO"
            self.audios += 1


        else:

            tipo="OTRO"
            self.otros +=1


        try:

            stat = path.stat()


            return {

                "ruta": str(path),

                "nombre": path.name,

                "extension": extension,

                "tamano": stat.st_size,

                "fecha_modificacion":
                    str(stat.st_mtime),

                "tipo": tipo
            }


        except Exception:

            return None