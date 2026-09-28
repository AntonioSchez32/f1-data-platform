select
    season::integer as season,
    round::integer as round,
    DriverNumber as driver_number,
    Abbreviation as driver_code,
    FullName as full_name,
    TeamName as team_name,
    '#' || nullif(TeamColor, '') as team_color,
    HeadshotUrl as headshot_url,
    Position::integer as position,
    GridPosition::integer as grid_position,
    Status as status,
    Points as points
from {{ source('fastf1', 'results') }}
