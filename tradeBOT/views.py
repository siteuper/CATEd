import json
import time
import datetime
from django.db.models import Sum
from django.http import HttpResponse
from django.shortcuts import render, redirect
from trade.models import UserExchanges, Exchanges
from tradeBOT.models import ExchangeCoin, Pair, ExchangeMainCoin, UserMainCoinPriority, \
    ExchangeTicker, UserPair, ToTrade
from django.core.serializers.json import DjangoJSONEncoder


def setup(request, pk):
    args = {}
    try:
        args['user_exchange'] = UserExchanges.objects.get(pk=pk, user=request.user)
        args['user_pairs'] = UserPair.objects.filter(user=request.user,
                                                     user_exchange=args['user_exchange']).order_by(
            '-rank')
        args['primary_coins'] = ExchangeMainCoin.objects.filter(coin__exchange=args['user_exchange'].exchange).order_by(
            'coin__symbol')
        args['to_trade'] = ToTrade.objects.filter(user_pair__user_exchange=args['user_exchange']).order_by(
            'date_updated')
    except UserExchanges.DoesNotExist:
        return redirect('index')
    return render(request, 'tradeBOT/setup.html', args)


def add_user_pair(request):
    if request.method == 'POST':
        pair_pk = request.POST.get('pair')
        user_exchange_pk = request.POST.get('user-exchange')
        try:
            pair = Pair.objects.get(pk=pair_pk)
            user_pair = UserPair.objects.get_or_create(user=request.user, pair=pair, user_exchange_id=user_exchange_pk)
        except Pair.DoesNotExist:
            pass
        return redirect('/trade/setup/' + str(user_exchange_pk) + '/')


def change_rank(request):
    if request.is_ajax():
        pair_id = request.POST.get('pair_id')
        type_c = request.POST.get('type')
        try:
            user_pair = UserPair.objects.get(pk=pair_id, user=request.user)
            if type_c == 'up':
                user_pair.rank = user_pair.rank + 1
                user_pair.save()
            elif type_c == 'down':
                if user_pair.rank > 1:
                    user_pair.rank = user_pair.rank - 1
                    user_pair.save()
        except UserPair.DoesNotExist:
            return HttpResponse('false', status=200)
    return HttpResponse('ok', status=200)


def set_share(request):
    if request.is_ajax():
        user_pair_id = request.POST.get('pair_id')
        share = request.POST.get('share')
        if int(share) < 0:
            return HttpResponse('Invalid request', status=200)
        user_exch = request.POST.get('user_exch')
        if int(share) == 0:
            try:
                user_pair = UserPair.objects.get(pk=user_pair_id, user=request.user)
                user_pair.share = 0
                user_pair.save()
            except UserPair.DoesNotExist:
                return HttpResponse('Not your pair', status=200)
            return HttpResponse('ok', status=200)
        user_pair_share_summ = \
            UserPair.objects.filter(user=request.user, user_exchange__pk=user_exch).exclude(pk=user_pair_id).aggregate(
                Sum('share'))['share__sum']
        if user_pair_share_summ is None:
            user_pair_share_summ = 0
        if float(user_pair_share_summ) + float(share) > 100:
            return HttpResponse('Sum shares cant be more than 100', status=200)
        try:
            user_pair = UserPair.objects.get(pk=user_pair_id, user=request.user)
            user_pair.share = share
            user_pair.save()
        except UserPair.DoesNotExist:
            return HttpResponse('Not your coin', status=200)
        return HttpResponse('ok', status=200)


def delete_user_pair(request):
    if request.is_ajax():
        user_pair_id = request.POST.get('pair_id')
        try:
            user_pair = UserPair.objects.get(pk=user_pair_id, user=request.user).delete()
        except UserPair.DoesNotExist:
            return HttpResponse('Not your pair', status=200)
    return HttpResponse('ok', status=200)


def relations(request):
    args = {'exchanges': Exchanges.objects.all()}
    return render(request, 'tradeBOT/relations.html', args)


def change_user_exchange_script_activity(request):
    if request.is_ajax():
        user_exch_id = request.POST.get('user_exch')
        try:
            user_exch = UserExchanges.objects.get(pk=user_exch_id, user=request.user)
            user_exch.is_active_script = not user_exch.is_active_script
            user_exch.save()
            return HttpResponse('true', status=200)
        except UserExchanges.DoesNotExist:
            return HttpResponse('false', status=200)


def change_primary_coin(request):
    if request.is_ajax():
        user_exch_pk = request.POST.get('user_exch')
        ue = UserExchanges.objects.get(pk=user_exch_pk)
        coin_pk = request.POST.get('coin')
        coin = ExchangeMainCoin.objects.get(pk=coin_pk)
        try:
            user_primary_coin = UserMainCoinPriority.objects.get(user_exchange=ue, main_coin=coin)
            user_primary_coin.is_active = not user_primary_coin.is_active
            user_primary_coin.save()
        except UserMainCoinPriority.DoesNotExist:
            new_user_primary_coin = UserMainCoinPriority()
            new_user_primary_coin.main_coin = coin
            new_user_primary_coin.priority = 1
            new_user_primary_coin.user_exchange = ue
            new_user_primary_coin.is_active = False
            new_user_primary_coin.save()
        return HttpResponse('ok', status=200)


def change_primary_coin_rank(request):
    if request.is_ajax():
        type_r = request.POST.get('type')
        ue_pk = request.POST.get('user_exch')
        coin_pk = request.POST.get('coin')
        ue = UserExchanges.objects.get(pk=ue_pk)
        coin = ExchangeMainCoin.objects.get(pk=coin_pk)
        try:
            user_primary_coin = UserMainCoinPriority.objects.get(user_exchange=ue, main_coin=coin)
            if type_r == 'up':
                user_primary_coin.priority += 1
            elif type_r == 'down':
                if user_primary_coin.priority > 1:
                    user_primary_coin.priority -= 1
            user_primary_coin.save()
        except UserMainCoinPriority.DoesNotExist:
            new_user_primary_coin = UserMainCoinPriority()
            new_user_primary_coin.main_coin = coin
            if type_r == 'up':
                new_user_primary_coin.priority = 2
            else:
                new_user_primary_coin.priority = 1
            new_user_primary_coin.user_exchange = ue
            new_user_primary_coin.is_active = True
            new_user_primary_coin.save()
        return HttpResponse('ok', status=200)


def get_ticker(request):
    if request.is_ajax():
        return HttpResponse('ok', status=200)


def set_pair_add(request):
    if request.method == 'POST':
        pair_pk = request.POST.get('pair-pk')
        user_exchange_pk = request.POST.get('user-exchange-pk')
        rate_of_change = request.POST.get('rate_of_change')
        if rate_of_change == '':
            rate_of_change = 0
        try:
            UserPair.objects.filter(pk=pair_pk, user_exchange_id=user_exchange_pk).update(
                rate_of_change=rate_of_change)
        except UserPair.DoesNotExist:
            pass
        return redirect('/trade/setup/' + str(user_exchange_pk) + '/')
    else:
        return redirect('/')


def get_new_to_trade(request):
    if request.is_ajax():
        ue_pk = request.POST.get('user_exch')
        already = request.POST.get('already')
        to_trade = ToTrade.objects.filter(user_pair__user_exchange_id=ue_pk)
        if len(to_trade) != int(already):
            return render(request, 'tradeBOT/to_trade.html', {'to_trade': to_trade})
        else:
            return HttpResponse('ok', status=200)


def exchange_depth_to_trade(request):
    if request.method == 'POST':
        depth = request.POST.get('depth')
        exchange_pk = request.POST.get('user-exchange-pk')
        if depth == '':
            depth = 0
        try:
            ue = UserExchanges.objects.get(user=request.user, pk=exchange_pk)
            ue.coefficient_of_depth = depth
            ue.save()
        except UserExchanges.DoesNotExist:
            pass
        return redirect('/trade/setup/' + str(exchange_pk) + '/')
    else:
        return HttpResponse('Please use POST request', status=200)
