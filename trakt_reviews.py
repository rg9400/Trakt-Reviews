#!/usr/bin/env python
import requests
import os
import sys
from logging.handlers import RotatingFileHandler 
from logging import DEBUG, INFO, getLogger, Formatter, StreamHandler
from plexapi.server import PlexServer
import sqlite3

################################ CONFIG BELOW ################################
PLEX_URL = 'http://localhost:32400'
PLEX_TOKEN = "YOURTOKEN"
TRAKT_CLIENT_ID = "YOURTRAKTCLIENTID"
TRAKT_USER_ID = "YOURTRAKTUSERID"
###############################################################################

## CODE BELOW ##

# Set up the rotating log files
size = 10*1024*1024  # 5MB
max_files = 5  # Keep up to 5 logs
log_path = os.environ.get('LOG_FOLDER', os.path.dirname(sys.argv[0]))
log_filename = os.path.join(log_path, 'trakt_reviews.log')
file_logger = RotatingFileHandler(log_filename, maxBytes=size, backupCount=max_files)
console = StreamHandler()
logger_formatter = Formatter('[%(asctime)s] %(name)s - %(levelname)s - %(message)s')
console_formatter = Formatter('%(message)s')
console.setFormatter(console_formatter)
file_logger.setFormatter(logger_formatter)
log = getLogger('Trakt Reviews')
console.setLevel(INFO)
file_logger.setLevel(INFO)
log.addHandler(console)
log.addHandler(file_logger)

def check_if_values_match(db_file, table_name, id, timestamp):
    """
    Checks if the values in a dictionary match the corresponding rows in a database table.

    Args:
        db_file (str): Path to the SQLite database file.
        table_name (str): Name of the table in the database.
        dictionary (dict): Dictionary containing the key-value pairs to check.
    """

    con = sqlite3.connect(db_file)
    cursor = con.cursor()
    
    query = f"SELECT * FROM {table_name} WHERE id = ?"
    cursor.execute(query, (id,))
    result = cursor.fetchone()

    if not result:
        log.warning(f"Need to process comment {id}")
        con.close()
        return False

    if result and timestamp not in result:
        log.warning(f"Need to update comment {id} for timestamp {timestamp}")
        con.close()
        return False

    con.close()
    return True

def main():
    #Check if database and table exist, else create them
    db_file = os.path.join(os.path.dirname(sys.argv[0]), 'reviews.db')
    table_name = 'reviews'
    con = sqlite3.connect(db_file)
    cur = con.cursor()

    try:
        cur.execute("SELECT * FROM {}".format(table_name))
    except sqlite3.OperationalError:
        log.warning("Need to create reviews table")
        if sqlite3.OperationalError:
            try:
                cur.execute("CREATE TABLE reviews(id type UNIQUE, updated_at)")
            except sqlite3.Error() as e:
                log.warning(e, " occured")
    con.commit()
    con.close()

    # Various constants
    plex = PlexServer(PLEX_URL, PLEX_TOKEN)
    trakt_headers = {"content-type": "application/json", "trakt-api-version": "2", "trakt-api-key": TRAKT_CLIENT_ID, 'User-agent': 'Plex Review Integrator v0.1'}
    trakt_url = 'https://api.trakt.tv/users/{}/comments?limit=9999999'.format(TRAKT_USER_ID)
    plex_url = 'https://community.plex.tv/api?X-Plex-Token={}'.format(PLEX_TOKEN)
    query = "\n    mutation createReview($input: CreateReviewInput!, $skipUserState: Boolean = false) {\n  createReview(input: $input) {\n    ...ActivityReviewFragment\n  }\n}\n    \n    fragment ActivityReviewFragment on ActivityReview {\n  ...activityFragment\n  reviewRating: rating\n  hasSpoilers\n  message\n  updatedAt\n  status\n  rejectionReasons\n  updatedAt\n}\n    \n\n    fragment activityFragment on Activity {\n  __typename\n  commentCount\n  date\n  id\n  isMuted\n  isPrimary\n  privacy\n  reaction\n  reactionsCount\n  reactionsTypes\n  metadataItem {\n    ...itemFields\n  }\n  userV2 {\n    id\n    username\n    displayName\n    avatar\n    friendStatus\n    isMuted\n    isHidden\n    isBlocked\n    mutualFriends {\n      count\n      friends {\n        avatar\n        displayName\n        id\n        username\n      }\n    }\n  }\n}\n    \n\n    fragment itemFields on MetadataItem {\n  id\n  images {\n    coverArt\n    coverPoster\n    thumbnail\n    art\n  }\n  userState @skip(if: $skipUserState) {\n    viewCount\n    viewedLeafCount\n    watchlistedAt\n  }\n  title\n  key\n  type\n  index\n  publicPagesURL\n  parent {\n    ...parentFields\n  }\n  grandparent {\n    ...parentFields\n  }\n  publishedAt\n  leafCount\n  year\n  originallyAvailableAt\n  childCount\n}\n    \n\n    fragment parentFields on MetadataItem {\n  index\n  title\n  publishedAt\n  key\n  type\n  images {\n    coverArt\n    coverPoster\n    thumbnail\n    art\n  }\n  userState @skip(if: $skipUserState) {\n    viewCount\n    viewedLeafCount\n    watchlistedAt\n  }\n}\n    "

    # Pull user's list of reviews
    try:
        trakt_reviews = requests.get(trakt_url, headers=trakt_headers).json()
    except:
        log.warning("Trakt user page for {} inaccessible".format(TRAKT_USER_ID))

    # Only process new reviews
    new_reviews = []
    for review in trakt_reviews:
        comment_id = review['comment']['id']
        comment_timestamp = review['comment']['updated_at']
        if not check_if_values_match(db_file, table_name, comment_id, comment_timestamp):
            new_reviews.append(review)

    # Build guid inventory from Plex libraries if there are new reviews
    if new_reviews:
        guidLookup = {}
        for library in plex.library.sections():
            if library.type in ('show', 'movie'):
                for item in library.all():
                    guidLookup[item.guid] = item
                    guidLookup.update({guid.id: item for guid in item.guids})
    
    # Start checking new reviews
    for review in new_reviews:
        comment = review['comment']['comment']
        spoiler = review['comment']['spoiler']
        comment_id = review['comment']['id']
        comment_timestamp = review['comment']['updated_at']
        type = review['type']

        #We pull ratings if they exist
        rating = review['comment'].get('user_rating', None)
        metadata = None

        #Pull Plex metadata/guid for the various reviews if they exist
        if type == 'movie':
            title = review['movie']['title']
            imdb = review['movie']['ids']['imdb']
            try:
                movie = guidLookup['imdb://{}'.format(imdb)]
                guid = movie.guid
                metadata = guid.split('plex://movie/', 1)[1]
            except:
                log.warning('Cannot find movie {} with IMDb ID {} in Plex Library'.format(title, imdb))

        elif type =='show':
            title = review['show']['title']
            imdb = review['show']['ids']['imdb']
            try:
                show = guidLookup['imdb://{}'.format(imdb)]
                guid = show.guid
                metadata = guid.split('plex://show/', 1)[1]
            except:
                log.warning('Cannot find show {} with IMDb ID {} in Plex Library'.format(title, imdb))

        elif type =='season':
            title = review['show']['title']
            imdb = review['show']['ids']['imdb']
            season_number = review['season']['number']
            try:
                show = guidLookup['imdb://{}'.format(imdb)]
                season = show.season(season_number)
                guid = season.guid
                metadata = guid.split('plex://season/', 1)[1]
            except:
                log.warning('Cannot find show {} season {} with IMDb ID {} in Plex Library'.format(title, season_number, imdb))

        elif type == "episode":
            title = review['show']['title']
            season_number = review['episode']['season']
            episode_number = review['episode']['number']
            try:
                show = guidLookup['imdb://{}'.format(imdb)]
                episode = show.episode(season=season_number,episode=episode_number)
                guid = episode.guid
                metadata = guid.split("plex://episode/", 1)[1]
            except:
                log.warning("Cannot find show {} season {} episode with IMDb ID {} in Plex Library".format(title, season_number, episode_number, imdb))

        else:
            log.warning("Review type for {} not supported".format(type))

        # If item's Plex guid was found, send the review to Plex
        if metadata:
            #Truncate review to 10000 characters due to Plex limit
            message = comment[:10000] if len(comment) > 10000 else comment
            input = {"metadata":metadata, "hasSpoilers": spoiler, "message": message}
            if rating:
                input['rating'] = rating
            variables = {'input': input}

            response = requests.post(plex_url, json={'query': query, 'variables': variables, 'operationName': 'createReview'})
            
            response_data = response.json()
            status_code = response.status_code
            status = response_data.get('data', {}).get('createReview', {}).get('status', None)

            # If review was successful, add to DB to prevent future processing
            if status_code == 200 and status in ("PENDING", "PUBLISHED"):
                log.warning(f"Review for {comment_id} updated on Plex")
                con = sqlite3.connect(db_file)
                cur = con.cursor()
                insert = (comment_id, comment_timestamp)
                cur.execute("""
                    INSERT INTO reviews VALUES
                        {}
                            ON CONFLICT(id) DO UPDATE SET updated_at=excluded.updated_at
                """.format(insert))
                con.commit()
                con.close()
            else:
                log.warning("Review was not successfuly submitted to Plex. Status Code is {}, Status is {}, and reponse was {}".format(status_code, status, response.json()))

if __name__ == "__main__":
    main()
