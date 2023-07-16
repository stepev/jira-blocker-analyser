# jira-blocker-analyser
## Blocker clustering
"Blocker clustering" is one of the key important practices of the Kanban method, designed to reveal anв review obstacles or "blockers" that slow down the workflow and affects work items Lead Time. In practice, blockers are what prevent tasks from being carried out and stop their movement on the Kanban board.

The essence of the "Blocker clustering" practice lies in the gathering of blocker information, their categorisation, and analysis. This helps teams see common patterns, understand the causes behind these obstacles and find solutions for their elimination. Essentially, it is a practice of risk management.

The main stages of the practice are as follows:

1. Marking of blocking items: It is important to identify and mark blocked and blocking work items clearly so that they are visible to the entire team.
2. Collecting data on blockers: Information is gathered about the blockers, including the duration of the blocking, impact on tasks, and reasons behind the blockage.
3. Clustering of blockers: Blockers are then clustered according to common reasons or themes. This may be done together with the team during a joint analysis process.
4. Selection of solutions and their implementation: Based on the common reasons behind blockages, the team formulates actions for their elimination and more effective management of the working process.

## Accounting for Blockers in Jira
A common practice for accounting for blockers in Jira is marking blocked tasks with a flag. This is very convenient from a visualization perspective, they are immediately visible on the Kanban board. But for analysis, one has to manually review comments and task history.

## Script for Gathering Information on Flag Blockers in Jira
The script will automatically find out when the blockage started and when it ended. You can easily see how long a task was blocked. This helps teams start improving their processes and getting rid of obstacles.

A peculiar feature of the script is collecting comments that were left during the blocking period. This makes it possible to understand what was happening with the task during the blocking period. Moreover, you can organise the output of data the way that is convenient for you: you can view the result right in the console, or save it in CSV or Excel format for further analysis.

The script connects via API to your Jira, selects all tasks that have ever been flagged, and for each block it outputs:

* Issue key
* Task title (Issue Summary)
* Date and time of setting and lifting the blockage (flag)
    *  If flag was not removed, the moment of the first issue status change is uded instead. Additionally this fact is marked, so the team can check if they manage flags properly.
*  Total blocking time
*  Blocker category
    * The script looks in comments for a word beginning with # and consider this word as a blocker category name
* All comments during the blocked period

## Command Line
The following command line parameters are provided:

**--jira-server**: Specify the URL of your Jira server

**--project**: Optional. This parameter defines the name of the Jira project you want to analyze.

**--team**: Optional. If several teams work in one project and you use the team field to distinguish them, specify the value

**--jql**: Optional. Set the JQL filter to select tasks from Jira for analysis, in addition to or instead of project and team parameters. Do not use your JQL project and team if you specify them in command line attributes. Do not use in your JQL condition "resolutiondate> = ...", use the command line attribute --date instead. Do not use in JQL condition ' and comment ~ "(flag) Flag added"', it will be added automatically. Do not use in JQL "ORDER by ...".

**--date**: Optional. This parameter defines the start date for analysis. It limits the search for tasks that were closed after the specified date. If you have not specified a value, by default the script processes tasks for the last 30 days.

**--user**: Here, specify the name of the Jira user.

**--password**: This is the password for the Jira account specified in the --user parameter.

**--mode**: Optional. This parameter defines how to display the results of the analysis. The parameter can take values 'print', 'csv', 'xlsx', which corresponds to displaying information in the console in text format, in a csv file or Excel file, respectively. By default, 'print' is selected.

**--output-file**: Optional. The name of the file without the extension to save the results, if the --mode parameter is set as 'csv' or 'xlsx'. By default, 'blockers' is used. The script adds the current date and time to the filename.

**--category-pattern**: Optional. regexp pattern for searching in a comment the blocking category. By default, a word beginning with '#' is searched for. If you use another method, set the search criteria for it here

Working with the script is simple: set the values you need for the listed parameters, and the script will get from Jira all tasks in the specified project, closed starting from the specified date, which had at least once been flagged and will perform block analysis according to the specified parameters. You can set your default values by editing the script. Be careful, it is not recommended to save the password in the script.

## Feedback
Please create an issue here at github if you found any problems in the script or want to propose an improvement. Contrubition is welcome as well.
