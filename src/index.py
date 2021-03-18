import json
import os
import re
import logging
import boto3
from botocore.exceptions import ClientError

# Setup logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Set environment variables
USE_EXISTING_LOG_GROUPS = os.environ['USE_EXISTING_LOG_GROUPS']
LOG_GROUP_TAGS = os.environ['LOG_GROUP_TAGS']
LOG_GROUP_PATTERN = os.environ['LOG_GROUP_PATTERN']
LAMBDA_ARN = os.environ['LAMBDA_ARN']

cwl = boto3.client('logs')


def subscribe_to_lambda(log_group_name):
    """Subscribes a log group to Lambda"""
    try:
        response = cwl.put_subscription_filter(
            destinationArn=LAMBDA_ARN,
            filterName='SplunkFilter',
            filterPattern='',
            logGroupName=log_group_name
        )
        logger.info(f'Log group {log_group_name} subscribed to Lambda')
    except Exception as error:
        logger.error(f'Error subscribing log group to Lambda')
        raise error


def filter_log_groups(event):
    """Filter log groups on pattern/tags"""
    try:
        log_group_name = event['detail']['requestParameters']['logGroupName']
        # Match the given pattern against the event resource name
        if re.match(LOG_GROUP_PATTERN, log_group_name) and event['detail']['eventName'] == "CreateLogGroup":
            logger.debug(f'Pattern match for new log group')
            return True
        log_group_tags = event['detail']['requestParameters']['tags']
        # If tags are specified and the resource has tags
        if LOG_GROUP_TAGS and log_group_tags:
            logger.info(f'Tags in log group: {log_group_tags}')
            tags_array = LOG_GROUP_TAGS.split(",")
            for i in tags_array:
                tag = tags_array[i].split("=")
                key = tag[0].strip()
                value = tag[1].strip()
                if log_group_tags[key] and log_group_tags[key] == value:
                    logger.debug(f'Tag match for new log group')
                    return True
        logger.debug(f'No pattern or tag match on new log group')
        return False
    except Exception as error:
        logger.error(f'Error filtering log groups on pattern/tags')
        raise error


def subscribe_existing_log_groups(log_groups):
    """Create subscription filter for Lambda on existing log groups"""
    logger.info(f'Subscribing existing log groups to Lambda')
    try:
        for log_group in log_groups:
            log_group_name = log_group['logGroupName']
            if re.match(LOG_GROUP_PATTERN, log_group_name):
                logger.debug(f'Pattern match for existing log group')
                response = subscribe_to_lambda(log_group_name)
    except Exception as error:
        logger.error(f'Error filtering log groups on pattern/tags')
        raise error


def process_existing_log_groups():
    """Processes existing Log Groups"""
    try:
        # Paginate through existing log groups
        paginator = cwl.get_paginator('describe_log_groups')
        response_iterator = paginator.paginate()
        for page in response_iterator:
            logger.info('Sending batch of existing log groups to subscriber')
            # Send page of log groups to subscriber function
            response = subscribe_existing_log_groups(page['logGroups'])
            logger.debug(f'Subscribe existing log groups response: {response}')
    except Exception as error:
        logger.error(f'Error filtering log groups on pattern/tags')
        raise error


def process_events(event):
    """Process incoming event for new log group"""
    try:
        log_group_name = event['detail']['requestParameters']['logGroupName']
        logger.info(f'Processing event for {log_group_name}')
        # Check if log group matches filter
        if filter_log_groups(event):
            logger.info(f'Subscribing {log_group_name} to Lambda')
            response = subscribe_to_lambda(log_group_name)
            logger.debug(f'Subscribe to lambda response: {response}')
        else:
            logger.warning(f'Log group {log_group_name} did not match pattern/tags')
    except Exception as error:
        logger.error(f'Error subscribing log group to Lambda')
        raise error


def lambda_handler(event, context):
    """Main function handler"""
    # Output the event
    logger.info(json.dumps(event))
    try:
        if USE_EXISTING_LOG_GROUPS == "true":
            process_existing_log_groups()
        else:
            process_events(event)
    except Exception as error:
        logger.error(error)
        raise error
