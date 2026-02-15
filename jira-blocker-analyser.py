# -*- coding: utf-8 -*-
import argparse
import re
from jira import JIRA
from datetime import datetime, timedelta
from bisect import bisect_right
import csv
import pandas as pd
#from yaspin import yaspin
#from yaspin.spinners import Spinners

def process_issue(jira, issue):
    issue = jira.issue(issue.key, expand='changelog')  # получаем историю изменений задачи
    changelog = issue.changelog

    flag_set_time = None
    flag_removed_time = None
    status_change_times = []
    comments = issue.fields.comment.comments
    blocker_infos = []

    for history in changelog.histories:
        history_created_time = datetime.strptime(history.created, '%Y-%m-%dT%H:%M:%S.%f%z')
        for item in history.items:
            if item.field == 'status':
                status_change_times.append(history_created_time)
            if item.field == 'Flagged':
                if item.toString == 'Impediment':
                    flag_set_time = history_created_time
                elif item.fromString == 'Impediment':
                    flag_removed_time = history_created_time

            # Если установлены и время установки, и время снятия флага, выводим информацию о блокировке и сбрасываем переменные
            if flag_set_time and flag_removed_time:
                blocker_info = blocker_info_to_dict(issue, flag_set_time, flag_removed_time, comments, False)
                blocker_infos.append(blocker_info)
                flag_set_time = None
                flag_removed_time = None

    # If the flag is still set at the end of history, use the last status change time as the flag removed time
    if flag_set_time and not flag_removed_time:
        flag_removed_time = status_change_times[-1]  # Use the last status change time
        blocker_info = blocker_info_to_dict(issue, flag_set_time, flag_removed_time, comments, True)
        blocker_infos.append(blocker_info)

    return blocker_infos

def blocker_info_to_dict(issue, flag_set_time, flag_removed_time, comments, flag_was_not_removed):
    info_dict = dict()
    info_dict['Issue Key'] = issue.key
    info_dict['Issue Summary'] = issue.fields.summary
    info_dict['Flag Set Time'] = flag_set_time.strftime('%Y-%m-%d %H:%M')
    info_dict['Flag Removed Time'] = flag_removed_time.strftime('%Y-%m-%d %H:%M')

    time_flagged = flag_removed_time - flag_set_time
    info_dict['Time Blocked'] = time_flagged.total_seconds()  # always in seconds

    info_dict['Blocker Category'] = blocker_category_from_comment(comments, flag_set_time, category_pattern)
    info_dict['Comments'] = comments_text(comments, flag_set_time, flag_removed_time)

    info_dict['Flag was not removed'] = flag_was_not_removed

    return info_dict

def blocker_category_from_comment(comments, flag_set_time, category_search_pattern):
    for comment in comments:
#        category_search_pattern = r"#\w+"  # слово, начинающееся с #
#        category_search_pattern =  r'\{(.+?)\} # текст в фигурных скобках, {blocker+category}
        comment_time = datetime.strptime(comment.created.split(".")[0], '%Y-%m-%dT%H:%M:%S')
        if flag_set_time == comment_time:
            match = re.search(category_search_pattern, comment.body)
            if match:
                return match.group(0)
    return ""

def comments_text(comments, flag_set_time, flag_removed_time):
    text = ""
    for comment in comments:
        comment_time = datetime.strptime(comment.created, '%Y-%m-%dT%H:%M:%S.%f%z')
        if flag_set_time <= comment_time <= flag_removed_time:
            text += comment.body + '\n---\n'
    return text


def format_blocking_time(seconds, time_unit):
    """Convert seconds to display value in days or hours. Returns (value, unit_str)."""
    if time_unit == 'hours':
        return round(seconds / 3600, 1), 'hours'
    return round(seconds / 86400, 1), 'days'


def main():
    parser = argparse.ArgumentParser(description='Script for flagged blockers analysis')
    parser.add_argument('--jira-server', default='https://jira.domain.name', type=str, help='Jira server URL')
    parser.add_argument('--jql', type=str, help='Use additional JQL parameters to select issues to analyse. If you specified project or team in arguments, do not use same clause in the JQL. Do not speicify "resolutiondate >= ..." in the JQL, use "---date" argument instead') # add your full JQL or additional conditions if needed
    parser.add_argument('--project', type=str, help='Jira project key') # add your default project if needed
    parser.add_argument('--team', type=str, help='Jira team field, in case several teams are working in a single project') # add your default team if needed
    parser.add_argument('--date', default=(datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'), type=str, help='Start date')
    parser.add_argument('--user', default='username', type=str, help='User name')
    parser.add_argument('--password', default='password', type=str, help='Password')
    parser.add_argument("--mode", default='print', type=str, help="Output mode: print / csv / xlsx")
    parser.add_argument("--output-file", default='blockers', type=str, help="Output file name without extension, use with --mode: xlsx or csv")
    parser.add_argument('--category-pattern', default=r"#\w+", type=str, help='Pattern for searching a blocker category in comments')
    parser.add_argument('--time-unit', default='days', choices=['days', 'hours'], help='Output blocking time in days or hours')
    args = parser.parse_args()

    global jira
    jira = JIRA(server=args.jira_server, basic_auth=(args.user, args.password))
    global category_pattern
    category_pattern = args.category_pattern
    
    issues = []
    startAt = 0
    maxResults = 50

#   spinner = yaspin(text="Loading", color="yellow")
#    spinner.spinner = "|/-\\"
#with yaspin(spinner, text="Loading data from Jira", color="yellow") as spinner:

    jql_query = args.jql if args.jql else ''
    if args.project:
        jql_query += f' and project = {args.project}' if jql_query else f'project = {args.project}'
    if args.team:
        jql_query += f' and Team = {args.team}' if jql_query else f'Team = {args.team}'
    if args.date:
        jql_query += f' and resolutiondate >= {args.date}' if jql_query else f'resolutiondate >= {args.date}'
# Append the mandatory clause
    jql_query += f' and comment ~ "(flag) Flag added"'

    while True:
        chunk = jira.search_issues(jql_query, 
                               startAt=startAt,
                               maxResults=maxResults)
        if len(chunk) == 0:
            break
        issues.extend(chunk)
        startAt += maxResults
    
#        spinner.ok("OK")
    
    all_blocker_info = []

    print(f">>>>> Found {len(issues)} issues <<<<<\n\n")
    print (f'JQL query used: {jql_query}')


    for issue in issues:
        blocker_infos = process_issue(jira, issue)
        all_blocker_info.extend(blocker_infos)  # use extend instead of append to add each dictionary separately

        if args.mode == 'csv' or args.mode == 'xlsx':
            print('.', end='')
    print()

    print(f">>>>> Found {len(all_blocker_info)} blockers <<<<<\n\n")

    if args.mode == 'print':
        for blocker_info in all_blocker_info:
            display_value, unit_str = format_blocking_time(blocker_info['Time Blocked'], args.time_unit)
            print(f"\n>>> Issue: {blocker_info['Issue Key']} - {blocker_info['Issue Summary']} <<<\n")
            print(f"Block set:     {blocker_info['Flag Set Time']}")
            print(f"Block removed: {blocker_info['Flag Removed Time']}\n")
            if blocker_info['Flag was not removed']:
                print("Flag was not removed!!! First status change after flag set considered as blocker removed\n")
            print(f"Time blocked ({unit_str}): {display_value}\n=======\n")
            if blocker_info['Blocker Category']:
                print(f"Blocker category: {blocker_info['Blocker Category']}\n______")
            print(f"Comment: \n{blocker_info['Comments']}\n")

    elif args.mode == 'csv':
        now = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
        with open(f"{args.output_file}-{now.replace(':', '-')}.csv", "w", newline="") as csvfile:
            fieldnames = ['Issue Key', 'Issue Summary', 'Flag Set Time', 'Flag Removed Time', 'Time Blocked', 'Time Unit', 'Blocker Category', 'Comments', 'Flag was not removed']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for blocker_info in all_blocker_info:
                display_value, unit_str = format_blocking_time(blocker_info['Time Blocked'], args.time_unit)
                row = {**blocker_info, 'Time Blocked': display_value, 'Time Unit': unit_str}
                writer.writerow(row)

    elif args.mode == 'xlsx':
        now = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
        rows = []
        for blocker_info in all_blocker_info:
            display_value, unit_str = format_blocking_time(blocker_info['Time Blocked'], args.time_unit)
            rows.append({**blocker_info, 'Time Blocked': display_value, 'Time Unit': unit_str})
        df = pd.DataFrame(rows)
        df.to_excel(f'{args.output_file}-{now}.xlsx', index=False)

if __name__ == "__main__":
    main()
