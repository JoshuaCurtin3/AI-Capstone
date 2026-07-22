"""HTTP views for the API app.

Views must stay thin: parse the request, call the relevant domain service
(e.g. app.services.pipeline.analyze_email), and serialize the response. No
scoring or parsing logic should live here.
"""
