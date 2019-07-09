def generate_shard_query():
    for i in range(101, 129):
        print('''
                SELECT Ticket_Id
               , Zendesk_Tickets.Asset_Id
               , Zendesk_Tickets.Root_Cause
               , Zendesk_Tickets.Ticket_Creation_Reason
               , Zendesk_Tickets.Ticket_Origin
               , Zendesk_Tickets.Service_Partner
               , Zendesk_Tickets.Date_Ticket_Initially_Assigned'''
               f''',  omnidian_{i}.assets.latitude
               ,  omnidian_{i}.assets.longitude
               ,  omnidian_{i}.installed_by
               ,  omnidian_{i}.installation_date'''
               ,'''
                  FROM tara.Zendesk_Tickets
                  JOIN omnidian.assets
                  ON Zendesk_Tickets.Asset_Id = omnidian.assets.asset_id'''
              ,
               f'''
                  JOIN omnidian_{i}.assets
                  ON Zendesk_Tickets.Asset_Id = omnidian_{i}.assets.asset_id '''
             , '''WHERE Zendesk_Tickets.Ticket_Status = 'Closed'
                  AND Zendesk_Tickets.Service_Partner <> 'Omnidian Support Team'
                  AND Zendesk_Tickets.Service_Type = 'Field Service'
                  AND Zendesk_Tickets.Root_Cause <> 'unassigned' ''')