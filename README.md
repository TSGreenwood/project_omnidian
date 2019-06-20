# project_omnidian
Student Data Science Project with Omnidian

Omnidian Machine Learning Project
Tara Greenwood, June 2019

Objectives
Create a machine learning model that can, based on recorded telemetry, categorise assets into groups indicating potential service requirements.
Validate the results of this model's categorisation with training and testing data.
Build public-facing website which protects Omnidian’s proprietary  information, as well as the personal information of their clients. Moreover, I intend to communicate the process in detail to Omnidian for reproducibility and potential business use. While I am not currently an employee, my work does represent their brand. I will review text information with them to ensure the writing is an accurate and positive representation of their work.
Omnidian is hiring for their first Data Scientist.  They have had over 200 applicants, most of which have more education and experience than I. I plan to use the supportive environment here at Flatiron School to gather deep understanding of their data environment, their goals for the future, the up-to-date methodologies, the interpersonal rapport and the concrete business results that will give me an inside track to the job. 

Business Understanding
Omnidian monitors solar panel performance across the country, generally using data gathered from the transformers on site. This yields time series data, which is compared with expected output (modeled from location, weather, etc.). When there is a large difference between the two, Omnidian dispatches one of its contracted companies to go fix it. 
	Different problems may call for different fixes, and different contractors may have different specialties. Would an electrician be better equipped to handle this, or would a solar panel technician? On the other hand, this may be something the customer is responsible for; they may just need to clean their roof.
	I intend to build a model to categorize common problems to help inform the decision making process. While there is no substitute for good judgement, good statistical models can be very helpful.

Data Understanding and Preparation
	Omnidian has granted me access to their monitoring data within their MySQL database. This database is fragmented due to unforseen growth, so I will allocate extra time for wrangling. Moreover, the target information (how the problem was ultimately fixed) is in another, more recent database of tickets. I’ll need to be cognizant of primary keys when merging, since site information is referenced by asset_id, while problem information is referenced by ticket_id.

Modeling
	This is a classification task. The machine learning methods will ultimately depend on the nature of the data. One challenge may be the time and processing power required to train, test, and compare outcomes of several models. Appropriate categories will arise from the data and from conversations with Omnidian staff.

Additional goals for myself (my wishlist)
Build my own library of functions and deploy that as a module.
Develop a list of potential new projects and infrastructural improvements to implement in my future at Omnidian.
Build an ERD and database annotation.

Challenges
	There is no data scientist at Omnidian to guide me. I will need to develop strong skills in time series analysis, machine learning techniques, familiarity with their use of AWS and perhaps Sagemaker, facility with MySQL, use of Nearmaps, interfacing with the prediction software of their consultant CPR, and of course, great documentation practices. The essential domain knowledge is informal, so I’m spending a lot of time with their software engineers to learn and codify this for future use.
	Due to the proprietary and private nature of a lot of this information, I will need to be creative about how to deploy an interactive website for the public to understand this project. Moreover, uploading information to Github will require tact and support from my wonderful teachers and coaches here.
