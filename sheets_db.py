from google.oauth2.credentials import Credentials
from google.oauth2 import service_account
from googleapiclient.discovery import build
from datetime import datetime

class GoogleSheetsDB:
    def __init__(self, credentials_path, spreadsheet_id):
        self.credentials = service_account.Credentials.from_service_account_file(
            credentials_path,
            scopes=['https://www.googleapis.com/auth/spreadsheets']
        )
        self.spreadsheet_id = spreadsheet_id
        self.service = build('sheets', 'v4', credentials=self.credentials)
        self.sheet = self.service.spreadsheets()

    def get_all_records(self):
        result = self.sheet.values().get(
            spreadsheetId=self.spreadsheet_id,
            range='Records!A2:I'  # Assuming headers are in row 1
        ).execute()
        values = result.get('values', [])
        records = []
        for row in values:
            if len(row) >= 9:  # Make sure we have all fields
                record = Record(
                    id=len(records) + 1,  # Simple auto-increment
                    date_insertion=datetime.strptime(row[0], '%Y-%m-%d'),
                    nom_collab=row[1],
                    titre_profil=row[2],
                    support_ao=row[3],
                    source_ao=row[4],
                    nombre_cv=int(row[5]),
                    lien_annonce=row[6],
                    lien_drive=row[7]
                )
                records.append(record)
        return records

    def add_record(self, record):
        values = [[
            record.date_insertion.strftime('%Y-%m-%d'),
            record.nom_collab,
            record.titre_profil,
            record.support_ao,
            record.source_ao,
            str(record.nombre_cv),
            record.lien_annonce,
            record.lien_drive
        ]]
        body = {'values': values}
        self.sheet.values().append(
            spreadsheetId=self.spreadsheet_id,
            range='Records!A:I',
            valueInputOption='RAW',
            body=body
        ).execute()

    def update_record(self, record_id, record_data):
        # Find the row for this record
        all_records = self.get_all_records()
        row_number = None
        for i, r in enumerate(all_records, start=2):  # Start from 2 to account for headers
            if r.id == record_id:
                row_number = i
                break
        
        if row_number:
            range_name = f'Records!A{row_number}:I{row_number}'
            values = [[
                record_data.date_insertion.strftime('%Y-%m-%d'),
                record_data.nom_collab,
                record_data.titre_profil,
                record_data.support_ao,
                record_data.source_ao,
                str(record_data.nombre_cv),
                record_data.lien_annonce,
                record_data.lien_drive
            ]]
            body = {'values': values}
            self.sheet.values().update(
                spreadsheetId=self.spreadsheet_id,
                range=range_name,
                valueInputOption='RAW',
                body=body
            ).execute()

    def delete_record(self, record_id):
        # Since we can't easily delete rows in Google Sheets,
        # we'll mark it as deleted by clearing the row
        all_records = self.get_all_records()
        row_number = None
        for i, r in enumerate(all_records, start=2):
            if r.id == record_id:
                row_number = i
                break
        
        if row_number:
            range_name = f'Records!A{row_number}:I{row_number}'
            self.sheet.values().clear(
                spreadsheetId=self.spreadsheet_id,
                range=range_name
            ).execute()