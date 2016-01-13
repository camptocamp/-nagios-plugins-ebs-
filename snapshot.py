#!/usr/bin/env python

from datetime import datetime
import argparse
import boto3
import sys
import time

class ebs_snapshot:
    def __init__(self, args):

        self.__debug     = args.debug
        self.__profile   = args.profile
        self.__region    = args.region
        self.__pattern   = args.pattern
        self.__threshold = args.threshold

        session = boto3.session.Session(
                profile_name = self.__profile,
                region_name  = self.__region
                )

        self.__snaps = []

        self.out_status = 0
        self.out_msg = 'EBS Snapshots: up-to-date'

        self.__ec2_client = session.client('ec2')
        self.__get_snapshots()
        self.__check_status()


    def __print(self, string, level=1):
        '''
        Simple "print" wrapper: sends to stdout if debug is > 0
        '''
        if level <= self.__debug:
            print string

    def __get_snapshots(self):
        '''
        Get snapshots, filter on PATTERN value. Also replace TODAY if present.
        '''
        self.__print('Getting snapshots')
        today = time.strftime('%A')
        pattern = self.__pattern.replace('TODAY', today)
        self.__print('Filter snapshots with %s'%pattern)

        self.__snaps = self.__ec2_client.describe_snapshots(
                Filters=[
                    { 
                        'Name': 'description',
                        'Values': [
                            pattern
                            ],
                        }
                    ]
                )
        self.__print('There are %i snapshots matching the pattern' % len(self.__snaps['Snapshots']))

    def __check_status(self):
        if len(self.__snaps['Snapshots']) == 0:
            self.out_status = 2
            self.out_msg    = 'CRITICAL: no snapshot for "%s"' % self.__pattern
        elif len(self.__snaps['Snapshots']) > 1:
            self.out_status = 3
            self.out_msg    = 'UNKNON: more than two snapshot for "%s", unable to parse' % self.__pattern
        else:
            snap = self.__snaps['Snapshots'][0]
            progress = snap['Progress']
            if progress != '100%':
                self.out_status = 3
                self.out_msg    = 'UNKNOWN: apparently snapshot in progress, check later'
            if snap['StartTime'].date() != datetime.today().date():
                self.__print('No snapshot for today - checking threshold')
                if datetime.today().hour > self.__threshold:
                    self.out_status = 2
                    self.out_msg    = 'CRITICAL: no current snapshot for "%s"' % self.__pattern



if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Check if a current snapshot exists')
    parser.add_argument('--debug',  '-d',   help='Set verbosity level', default=0, type=int)
    parser.add_argument('--profile', '-p', help='Pass AWS profile name', default='default')
    parser.add_argument('--region', '-r',   help='Set AWS region', default='eu-west-1')
    parser.add_argument('--pattern', '-P', help='Matches Description field for snapshots. You might use TODAY as keyword.', required=True)
    parser.add_argument('--threshold', '-t', help='Delay after which we expect the volume to be available, in hours.', default='4', type=int)

    args = parser.parse_args()

    worker = ebs_snapshot(args)
    print worker.out_msg
    sys.exit(worker.out_status)
