# Plextrakt-Reviews
Pull reviews from Trakt into Plex. Only one way, does not push reviews from Plex into Trakt. It will also update the rating based on the one given in the review (if available). Should work for Movies, Shows, Seasons, and Episodes (though I have only tested with Movies and Seasons for now). This creates a sqlite database to prevent unnecessarily updating data on Plex end after processing reviews, so it should only update new reviews or when an item is added to Plex whose review has yet to be processed.

Please note that this uses the GraphQL community API for Plex which may not be officially supported and is directly hitting Plex's servers, not your own server. These reviews are published at Plex's community end but should only be visible to friends. 

Requires plexapi 4.4.1 or higher and requests. Run python -m pip install --upgrade plexapi requests with python replaced with whatever your python3 binary is to make sure you have the latest one.

## File Config

**PLEX_URL** - Set this to the local URL for your Plex Server

**PLEX_TOKEN** - Find your token by following the instructions here https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/. Note that not all the tokens I tried were able to work. If  you are getting a message saying it is not allowed, try turning on Network in Dev Tools, submitting a review, and checking the request headers for X-Plex-Token in the API call.

**TRAKT_CLIENT_ID** - You can create a Trakt account, then click *Your API Apps* under Settings, create a new app, give it a name. You can leave image, javascript, and the check-in/scrobble permissions blank, but you need to select a redirect uri. You can use the device authentication option listed in the help text or set something like google.com

**TRAKT_USER_ID** - the exact User ID (the one in the URL when you go to your profile after /users)
