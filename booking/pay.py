# encoding: utf8

"""
支付
"""

import os
import json
import copy
import logging
import datetime
import platform

from hack12306 import constants
from hack12306.pay import TrainPayAPI
from hack12306.utils import tomorrow, JSONEncoder

from . import settings
from . import exceptions
from .utils import get_public_ip

_logger = logging.getLogger('booking')


def test_pay(sequence_no, bank_id=constants.BANK_ID_WX, **kwargs):
    train_pay_api = TrainPayAPI()

    # 1.支付未完成订单
    pay_no_complete_order_result = train_pay_api.pay_no_complete_order(sequence_no, cookies=settings.COOKIES)
    _logger.debug('pay no complete order result. %s' % json.dumps(pay_no_complete_order_result, ensure_ascii=False,))
    if pay_no_complete_order_result['existError'] != 'N':
        raise exceptions.BookingOrderNoExists('%s订单不存在' % sequence_no)

    # 2.支付初始化
    train_pay_api.pay_init(cookies=settings.COOKIES)

    # 3.发起支付
    pay_check_new_result = train_pay_api.pay_check_new(cookies=settings.COOKIES)
    _logger.debug('pay check new result. %s' % json.dumps(pay_check_new_result, ensure_ascii=False))

    # 4.交易
    pay_business_result = train_pay_api.pay_web_business(
        pay_check_new_result['payForm']['tranData'],
        pay_check_new_result['payForm']['merSignMsg'],
        pay_check_new_result['payForm']['transType'],
        get_public_ip(), pay_check_new_result['payForm']['tranDataParsed']['order_timeout_date'],
        bank_id, cookies=settings.COOKIES)
    _logger.debug('pay business result. %s' % json.dumps(pay_business_result, ensure_ascii=False))

    # 5.跳转第三方支付
    pay_business_third_pay_resp = train_pay_api.submit(
        pay_business_result['url'],
        pay_business_result['params'],
        method=pay_business_result['method'],
        parse_resp=False,
        cookies=settings.COOKIES,
        allow_redirects=True)
    _logger.debug('pay third resp status code. %s' % pay_business_third_pay_resp.status_code)
    _logger.debug('pay third resp. %s' % pay_business_third_pay_resp.content)

    try:
        pay_filepath = settings.PAY_FILEPATH.format(date=datetime.date.today().stftime('%Y%m%d'),
                                                    order_no=sequence_no, bank_id=bank_id)
        if not os.path.exists(os.path.dirname(pay_filepath)):
            os.makedirs(os.path.dirname(pay_filepath))

        with open(pay_filepath, 'w') as f:
            f.write(pay_business_third_pay_resp.content)
    finally:
        if platform.mac_ver()[0]:
            os.system('open %s' % pay_filepath)
        else:
            if os.path.exists(pay_filepath):
                os.remove(pay_filepath)