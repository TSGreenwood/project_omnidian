# pull info from tables from all shards
#

def generate_shard_queries():
'''Note the shards are named "omnidian, omnidian_102, omnidian_103, omnidian_104, omnidian_105, omnidian_106, omnidian_107, omnidian_108, omnidian_109, omnidian_110, omnidian_111, omnidian_112, (no omnidian_113), omnidian_114, omnidian_115, omnidian_116, omnidian_117, omnidian_118, omnidian_119, omnidian_120,omnidian_121, omnidian_122, omnidian_123, omnidian_124, omnidian_125, omnidian_126, omnidian_127, and omnidian_128"'''
    for i in range(102, 129):
        if i == 113:
            continue
        query = f'''
         (SELECT Ticket_Id
        , Zendesk_Tickets.Asset_Id
        , Zendesk_Tickets.Root_Cause
        , Zendesk_Tickets.Ticket_Creation_Reason
        , Zendesk_Tickets.Ticket_Origin
        , Zendesk_Tickets.Service_Partner
        , Zendesk_Tickets.Date_Ticket_Initially_Assigned
        , omnidian_{i}.assets.latitude
        , omnidian_{i}.assets.longitude 
        , omnidian_{i}.assets.installed_by
        , omnidian_{i}.assets.installation_date
        FROM tara.Zendesk_Tickets 
        JOIN omnidian_{i}.assets
        ON tara.Zendesk_Tickets.Asset_Id = omnidian_{i}.assets.asset_id
        WHERE Zendesk_Tickets.Ticket_Status = 'Closed'
        AND Zendesk_Tickets.Service_Partner <> 'Omnidian Support Team'
        AND Zendesk_Tickets.Service_Type = 'Field Service'
        AND Zendesk_Tickets.Root_Cause <> 'unassigned')
        '''
        yield query
#Then:
mega_query = iter(generate_shard_queries())
#Then:
query_string = " UNION ".join(mega_query)
#Then:
df_all_num_shards_b = pd.read_sql(query_string, con=conn)
df_all_num_shards_b.info()