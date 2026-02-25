import logging

logger = logging.getLogger(__name__)

DEFAULT_PROJECTION = {
    "_id": 0,
    "api_player_id": 1,
    "image": 1,
    "name": 1,
    "display_name": 1,
}


def get_all_players(db, collection_name, *, filter_query=None, projection=None, limit=0):
    """
    Fetch player documents from the source collection.

    Args:
        db: The source Database instance.
        collection_name: Name of the players collection.
        filter_query: Optional MongoDB query dict. Default: {} (all).
        projection: Optional field projection.
        limit: Max documents to return. 0 = unlimited.

    Returns:
        List of player dicts.
    """
    collection = db[collection_name]
    query = filter_query or {}
    proj = projection or DEFAULT_PROJECTION

    cursor = collection.find(query, proj)
    if limit > 0:
        cursor = cursor.limit(limit)

    players = list(cursor)
    logger.info(f"Fetched {len(players)} players from {collection_name}")
    return players


def get_players_by_ids(db, collection_name, api_player_ids):
    """
    Fetch specific players by their api_player_id values.
    """
    return get_all_players(
        db,
        collection_name,
        filter_query={"api_player_id": {"$in": api_player_ids}},
    )
