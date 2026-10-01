{#- Grandes Premios (meetings) de OpenF1: el nombre sirve de control al casarlos con F1DB. -#}
select
    meeting_key::bigint as meeting_key,
    year::integer as season,
    meeting_name,
    meeting_official_name,
    country_name,
    location,
    coalesce(is_cancelled::boolean, false) as is_cancelled
from {{ bronze_source('openf1', 'meetings', 'openf1/meetings/*.parquet', {
    'meeting_key': 'bigint', 'year': 'bigint', 'meeting_name': 'varchar',
    'meeting_official_name': 'varchar', 'country_name': 'varchar', 'location': 'varchar',
    'is_cancelled': 'boolean'
}) }}
