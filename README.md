# project_omnidian

Omnidian Machine Learning Project
Tara Greenwood, June 2019

## Introduction

Clean energy is very important to me. That’s why I built a machine learning model to predict the root causes of field maintenance issues for a real company. Keeping overhead costs as low as possible is helpful for any business.

### About Onmnidian

Omnidian is a Seattle startup that ensures "solar without fear" to homeowners and businesses across the country. New solar owners can subscribe to  a 95% performance guarantee plan. If Omnidian can’t resolve it, they’ll actually pay subscribers for their loss of solar energy. 

Their software models expected output for each asset (solar panel generation site) and compares it with the actual output. If an asset underperforms, they take steps to fix it, often sending one of their service partners to address the issue. 

Omnidian gave me a wonderful opportunity to make alternative energy accessible to normal people. They generously gave me free access to their databases, their domain knowledge, and the autonomy to teach myself the skills necessary to build the models. It’s been a wonderful experience working with great people working to make the future better for all of us.

## Data Understanding 

Startups are lean and agile. They don’t always have a database administrator or engineer. Omnidian took over solar panel information from many different companies. Their databases are divided into 29 shards, and they had no entity relationship diagrams.

So I made some.

