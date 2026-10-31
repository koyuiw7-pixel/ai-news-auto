import unittest
from scripts.affiliate_price_audit import audit, parse_oz, parse_plaud


class TestAffiliatePriceAudit(unittest.TestCase):
    def test_plaud_variant_specific_and_availability(self):
        d={'title':'Plaud Note Pro','variants':[{'title':'Plaud Note Pro / Black','price':3080000,'available':True}, {'title':'Plaud Note Pro Flow Edition / Black','price':2970000,'available':True}]}
        self.assertEqual(parse_plaud(d), (30800,'available'))
        d['variants'][0]['available']=False
        self.assertEqual(parse_plaud(d), (30800,'sold_out'))
        del d['variants'][0]['available']
        self.assertEqual(parse_plaud(d), (None,'unknown'))

    def test_conflicting_or_missing_oz_status_is_unknown(self):
        self.assertEqual(parse_oz('<span data-id="makeshop-item-price:1">10,000</span><p class="item-stock">在庫あり</p>'),(10000,'available'))
        self.assertEqual(parse_oz('<span data-id="makeshop-item-price:1">10,000</span><div class="floating-buy-bar is-soldout">'),(10000,'sold_out'))
        self.assertEqual(parse_oz('<span data-id="makeshop-item-price:1">10,000</span>'),(10000,'unknown'))
        self.assertEqual(parse_oz('<p class="item-stock">在庫あり</p><div class="floating-buy-bar is-soldout">'),(None,'unknown'))

    def test_unknown_soldout_price_change_and_expired_are_distinct(self):
        offers={'partners':{'visible':{'name':'A','source':'x:a','price':200},'hidden':{'source':'x:b','hidden':True},'expired':{'source':'x:c','activeUntil':'2026-10-30T00:00:00+09:00'},'unmonitored':{'name':'D'}}}
        calls={'x:a':(100,'sold_out'),'x:b':(200,'sold_out'),'x:c':(200,'sold_out')}
        r=audit(offers,{},fetcher=lambda x:calls[x],checked_at='2026-10-31T00:00:00+09:00')
        self.assertEqual(r['reviewCount'],1)
        self.assertEqual(r['results'][0]['needsReview'],'sold_out_but_visible')
        self.assertEqual(r['counts']['not_monitored'],1)
        self.assertTrue(r['results'][2]['expired'])
        self.assertNotIn('needsReview',r['results'][1])

    def test_fetch_error_is_not_sold_out_or_success(self):
        def fail(_): raise TimeoutError('x')
        r=audit({'partners':{'x':{'source':'x'}}},{},fetcher=fail,checked_at='2026-10-31T00:00:00+09:00')
        self.assertEqual(r['results'][0]['availability'],'unknown')
        self.assertEqual(r['counts']['error'],1)

if __name__ == '__main__': unittest.main()
