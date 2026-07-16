#!/usr/bin/env python3
import argparse
import ast
import csv
import errno
import json
import logging
import os
import os.path
import re
from datetime import datetime, timedelta, timezone
from logging.handlers import RotatingFileHandler
from time import sleep

import pandas as pd
import requests
from dateutil.relativedelta import *

DEFAULT_CONFIG_PATH = 'andorra.json'
FILENAME = 'everynet-to-tp.log'
TPE_SAMPLE_FORMAT = os.path.join(os.path.dirname(__file__), 'tpe-sample-format.csv')
logger = logging.getLogger(__name__)


class UtcFormatter(logging.Formatter):
  def formatTime(self, record, datefmt=None):
    dt = datetime.fromtimestamp(record.created, tz=timezone.utc)
    return dt.isoformat(sep=' ', timespec='seconds')


def setup_logging():
  handler = RotatingFileHandler(
    FILENAME,
    maxBytes=10485760,
    backupCount=5,
    encoding="utf-8",
  )
  handler.setFormatter(UtcFormatter("%(asctime)s %(levelname)s %(message)s"))
  logger.setLevel(logging.INFO)
  logger.handlers.clear()
  logger.addHandler(handler)
  logger.propagate = False


def log_line(message):
  print(message)
  logger.info(message)


def make_params_org(access_token, org, limit):
  return {
    'access_token': access_token,
    'q': f'org:{org}',
    'sort': '-dev_eui',
    'offset': 0,
    'limit': limit
  }


def makenewdir(direc):
  try:
    os.makedirs(direc)
  except OSError as e:
    if e.errno != errno.EEXIST:
      raise


def slugify(value):
  slug = re.sub(r'[^A-Za-z0-9._-]+', '_', value).strip('_')
  return slug or 'org'


def format_counter(value):
  if pd.isna(value):
    return ''
  try:
    number = float(value)
  except (TypeError, ValueError):
    return str(value)
  if number.is_integer():
    return str(int(number))
  return str(number)


def format_tags(value):
  if isinstance(value, (list, tuple, set)):
    return ','.join(str(tag) for tag in value)
  if pd.isna(value):
    return ''
  if isinstance(value, str):
    try:
      parsed = ast.literal_eval(value)
    except (SyntaxError, ValueError):
      return value
    if isinstance(parsed, (list, tuple, set)):
      return ','.join(str(tag) for tag in parsed)
  return str(value)


def tpe_profile(row):
  activation = str(row.get('Activation', '')).upper()
  if activation:
    return f"CREATE_{activation}"
  return 'CREATE_OTAA'


def build_tpe_create_otaa_row(row, cp_value='', as_value='', rf2_value=''):
  return [
    'CREATE_OTAA',
    row.get('DevEUI', ''),
    row.get('Dev_Addr', ''),
    'LORA/GenericA.1.0.2c_ETSI',
    row.get('AppEUI', ''),
    row.get('AppKey', ''),
    '',
    cp_value,
    '',
    '',
    '',
    row.get('Lat', ''),
    row.get('Lng', ''),
    row.get('Org_Name', ''),
    '',
    '',
    'NEAR_STATIC',
    '',
    '',
    as_value,
    '',
    '',
    '',
    '',
    '',
    '',
    '',
    format_tags(row.get('Tags', '')),
    '',
    format_counter(row.get('FCNT_Down', '')),
    format_counter(row.get('FCNT_UP', '')),
    '',
    rf2_value,
    '0',
    '1',
    '',
    '',
    '',
    '',
    row.get('NWKSKey', ''),
    row.get('APPSkey', '')
  ]


def build_tpe_create_abp_row(row, cp_value='', as_value='', rf2_value=''):
  return [
    'CREATE_ABP',
    row.get('DevEUI', ''),
    row.get('Dev_Addr', ''),
    'LORA/GenericA.1.0.2c_ETSI',
    row.get('NWKSKey', ''),
    row.get('APPSkey', ''),
    '',
    cp_value,
    '',
    '',
    '',
    row.get('Lat', ''),
    row.get('Lng', ''),
    row.get('Org_Name', ''),
    '',
    '',
    'NEAR_STATIC',
    '',
    '',
    as_value,
    '',
    '',
    '',
    '',
    '',
    '',
    '',
    format_tags(row.get('Tags', '')),
    '',
    format_counter(row.get('FCNT_Down', '')),
    format_counter(row.get('FCNT_UP', '')),
    '',
    rf2_value,
    '0',
    '1',
    '',
    ''
  ]


def build_tpe_create_row(row, cp_value='', as_value='', rf2_value=''):
  if tpe_profile(row) == 'CREATE_ABP':
    return build_tpe_create_abp_row(row, cp_value, as_value, rf2_value)
  return build_tpe_create_otaa_row(row, cp_value, as_value, rf2_value)


def build_tpe_delete_row(row):
  return ['DELETE', row.get('DevEUI', '')] + [''] * 24


def load_tpe_create_template_rows():
  if not os.path.exists(TPE_SAMPLE_FORMAT):
    return []
  rows = []
  with open(TPE_SAMPLE_FORMAT, newline='') as fp:
    reader = csv.reader(fp)
    for row in reader:
      if row and not row[0].startswith('#'):
        break
      rows.append(row)
  return rows


def write_tpe_outputs(all_df, outputdir, cp_value='', as_value='', rf2_value=''):
  import_csvname = os.path.join(outputdir, 'all.import.csv')
  create_csvname = os.path.join(outputdir, 'all.create.csv')
  delete_csvname = os.path.join(outputdir, 'all.delete.csv')

  with open(import_csvname, 'w', newline='') as fp:
    wr = csv.writer(fp, dialect='excel')
    for _, row in all_df.iterrows():
      wr.writerow(build_tpe_create_row(row, cp_value, as_value, rf2_value))

  deveui_csvname = os.path.join(outputdir, 'deveui-list.csv')
  with open(deveui_csvname, 'w', newline='') as fp:
    wr = csv.writer(fp)
    for _, row in all_df.iterrows():
      wr.writerow([row.get('DevEUI', '')])

  with open(create_csvname, 'w', newline='') as fp:
    wr = csv.writer(fp, dialect='excel')
    for row in load_tpe_create_template_rows():
      wr.writerow(row)
    for _, row in all_df.iterrows():
      wr.writerow(build_tpe_create_row(row, '', as_value, rf2_value))

  with open(delete_csvname, 'w', newline='') as fp:
    wr = csv.writer(fp, dialect='excel')
    for _, row in all_df.iterrows():
      wr.writerow(build_tpe_delete_row(row))


def load_config(config_path):
  with open(config_path, 'r') as fp:
    config = json.load(fp)

  url = config.get('url')
  if not url:
    raise ValueError("Config must contain 'url'.")

  limit = config.get('limit')
  if not isinstance(limit, int) or limit <= 0:
    raise ValueError("Config must contain a positive integer 'limit'.")

  outputdir = config.get('outputdir')
  if not outputdir:
    raise ValueError("Config must contain 'outputdir'.")

  orgs = config.get('orgs')
  if not isinstance(orgs, list) or not orgs:
    raise ValueError("Config must contain a non-empty 'orgs' list.")

  return config


def fetch_devices(url, limit, access_token, org_id, org_name):
  result = []
  query_params = make_params_org(access_token, org_id, limit)

  while 1:
    req = requests.get(url, params=query_params)
    req.raise_for_status()
    data = req.json()
    devices = data['devices']

    result.extend(devices)
    log_line(f"{org_name}: {len(result)}")
    logger.info('Fetch {} devices. Total: {}'.format(len(devices), len(result)))

    if len(devices) < limit:
      break

    query_params['offset'] += limit
    sleep(0.1)

  return result


def build_output_frames(devices, org_name):
  one_month_ago = datetime.now() - timedelta(days=30)
  current_year = datetime.now().year
  enabled_dev = pd.DataFrame(devices)
  nan_value = float("NaN")
  enabled_dev.replace("", nan_value, inplace=True)

  def get_activity_status(last_activity):
    if pd.isna(last_activity):
      return 'Inactive'
    try:
      activity_time = datetime.fromtimestamp(last_activity)
      if activity_time.year == current_year:
        return 'Active'
      return 'Inactive'
    except (ValueError, TypeError):
      return 'Inactive'

  if 'last_activity' in enabled_dev.columns:
    enabled_dev['Activity_Status'] = enabled_dev['last_activity'].apply(get_activity_status)
  else:
    enabled_dev['Activity_Status'] = 'Inactive'

  column_mapping = {
    'dev_eui': 'DevEUI',
    'activation': 'Activation',
    'app_eui': 'AppEUI',
    'app_key': 'AppKey',
    'lorawan_version': 'MAC_Version',
    'dev_class': 'Class_Type',
    'dev_addr': 'Dev_Addr',
    'appskey': 'APPSkey',
    'nwkskey': 'NWKSKey',
    'counter_up': 'FCNT_UP',
    'counter_down': 'FCNT_Down',
    'last_activity': 'Last_Activity',
    'last_join': 'Last_Join',
    'tags': 'Tags',
    'band': 'Band'
  }
  mapped_df = enabled_dev.rename(columns=column_mapping)
  mapped_df['Org_Name'] = org_name

  if 'geolocation' in enabled_dev.columns:
    mapped_df['Lat'] = enabled_dev['geolocation'].apply(
      lambda g: g.get('lat', '') if isinstance(g, dict) else ''
    )
    mapped_df['Lng'] = enabled_dev['geolocation'].apply(
      lambda g: g.get('lng', '') if isinstance(g, dict) else ''
    )
  else:
    mapped_df['Lat'] = ''
    mapped_df['Lng'] = ''

  mapped_columns = ['Org_Name', 'DevEUI', 'Activation', 'AppEUI', 'AppKey', 'MAC_Version', 'Class_Type', 'Dev_Addr', 'APPSkey', 'NWKSKey', 'FCNT_UP', 'FCNT_Down', 'Last_Activity', 'Last_Join', 'Tags', 'Band', 'Activity_Status', 'Lat', 'Lng']
  mapped_df = mapped_df.reindex(columns=mapped_columns)

  return enabled_dev, mapped_df


def write_outputs(devices, outputdir, org_name):
  date_time = datetime.now().strftime('%Y_%m_%d_%Hh_%M')
  output_name = slugify(org_name)

  makenewdir(outputdir)

  jsonname = os.path.join(outputdir, date_time + '_' + output_name + '_Enabled Devices.json')
  csvname = os.path.join(outputdir, date_time + '_' + output_name + '_Enabled Devices.csv')
  mapped_csvname = os.path.join(outputdir, date_time + '_' + output_name + '_Mapped Enabled Devices.csv')

  logger.info(f"Saving results to file: {jsonname}")
  with open(jsonname, 'w') as f:
    json.dump(devices, f, sort_keys=True, indent=4)

  enabled_dev, mapped_df = build_output_frames(devices, org_name)
  enabled_dev.to_csv(csvname, index=False)
  mapped_df.to_csv(mapped_csvname, index=False)

  # csv_row = [date_time, org_name, number_active_dev, number_enable_dev, active_count]
  # with open(billing_name, "a") as fp:
  #   wr = csv.writer(fp, dialect='excel')
  #   wr.writerow(csv_row)

  # ~ print(f"✅ Billing Data for {org_name} has been recorded.")
  # ~ print(f"✅ Mapped Enabled Devices CSV saved to {mapped_csvname}")


def run_org(org_config, url, limit, outputdir):
  org_id = org_config.get('orgID')
  org_name = org_config.get('name')
  access_token = org_config.get('apiToken')

  if not org_id:
    raise ValueError("Each org config entry must contain 'orgID'.")
  if not org_name:
    raise ValueError("Each org config entry must contain 'name'.")
  if not access_token:
    raise ValueError(f"Org '{org_name}' is missing 'apiToken'.")

  devices = fetch_devices(url, limit, access_token, org_id, org_name)
  write_outputs(devices, outputdir, org_name)
  _, mapped_df = build_output_frames(devices, org_name)
  return mapped_df


def build_parser():
  parser = argparse.ArgumentParser(
    description="Extract Everynet devices for all orgs defined in a config file."
  )
  parser.add_argument(
    '-c',
    '--config',
    default=DEFAULT_CONFIG_PATH,
    help=f"Path to JSON config file. Defaults to {DEFAULT_CONFIG_PATH}."
  )
  parser.add_argument(
    '--cp',
    default='',
    help="Value for the TPE CP column in all.create.csv. Defaults to empty."
  )
  parser.add_argument(
    '--as',
    dest='as_value',
    default='',
    help="Value for the TPE ASID column in all.create.csv. Defaults to empty."
  )
  parser.add_argument(
    '--rx2freq',
    dest='rx2freq',
    nargs='?',
    const='869.525',
    default='',
    help="Set the TPE RF2 column in all.create.csv. Defaults to 869.525 when used without a value."
  )
  return parser


def main():
  setup_logging()
  parser = build_parser()
  args = parser.parse_args()
  config = load_config(args.config)

  current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
  log_line("----------------------------------------------------------")
  log_line(f"Starting device extraction at: {current_time}")
  rf2_value = args.rx2freq

  all_frames = []
  for org_config in config['orgs']:
    all_frames.append(run_org(org_config, config['url'], config['limit'], config['outputdir']))

  all_csvname = os.path.join(config['outputdir'], 'all.csv')
  if all_frames:
    all_df = pd.concat(all_frames, ignore_index=True)
    all_df.to_csv(all_csvname, index=False)
    write_tpe_outputs(all_df, config['outputdir'], args.cp, args.as_value, rf2_value)
  else:
    pd.DataFrame().to_csv(all_csvname, index=False)
    write_tpe_outputs(pd.DataFrame(), config['outputdir'], args.cp, args.as_value, rf2_value)

  log_line("Device extraction completed.")


if __name__ == "__main__":
  main()
