# -*- coding: utf-8 -*-

from django.db import models
import md5
import random
from dotpay.util import  STATUS_CHOICES,STATUS_CHOICES, generate_md5
from dotpay.settings import DOTPIN,DOTID,DOTORDERMODEL
from dotpay.signals import *

class DotRequest(models.Model):
    id_request = models.AutoField(primary_key=True)
    kwota = models.DecimalField(max_digits=5, decimal_places=1, help_text="Kwota transakcji  podana z częścią dziesiętną.")
    opis = models.CharField(max_length=255,help_text="Opis przeprowadzanej transakcji. ")
    control = models.CharField(max_length=128,help_text="Parametr kontrolny",unique=True)
    email = models.EmailField()
    
    def __unicode__(self):
        return u"%s" % self.opis
    
    def save(self,*args, **kwargs):
        self._gen_control()
        super(DotRequest, self).save(*args, **kwargs)
    
    def _gen_control(self):
        self.control = md5.new( str(self.kwota) + self.opis + str(random.randint(0,99999) ) ).hexdigest()



class DotResponse(models.Model):
    id_response = models.AutoField(primary_key=True)
    id = models.PositiveIntegerField(help_text="ID konta w systemie Dotpay, na rzecz którego dokonywana jest płatność (ID konta Sprzedawcy)")
    status = models.CharField(max_length=2, choices=STATUS_CHOICES,help_text="Informacja o ewentualnym wystąpieniu błędów na stronach serwisu Dotpay")
    control = models.CharField(max_length=128,help_text="Parametr kontrolny jeżeli został podany podczas przekazywania kupującego na strony serwisu Dotpay")
    t_id = models.CharField(max_length=100,help_text="Numer  identyfikacyjny transakcji nadany po księgowaniu na koncie użytkownika Dotpay (Sprzedawcy).")
    amount = models.DecimalField(max_digits=5, decimal_places=1, help_text="Kwota transakcji. Separatorem dziesiętnym jest znak kropki.")
    orginal_amount = models.CharField(max_length=100,help_text="Kwota transakcji i znacznik waluty (oddzielone znakiem spacji). Separatorem dziesiętnym jest znak kropki")
    t_status = models.CharField(max_length=1,choices=STATUS_CHOICES)
    description = models.CharField(max_length=255,null=True,blank=True,help_text="Pełna treść opisu transakcji.")
    md5 = models.CharField(max_length=32)    
    t_date = models.DateTimeField(null=True,blank=True,help_text="Data realizacji transakcji")
    request = models.ForeignKey(DotRequest,help_text="FK dla requestu")
    
    def __unicode__(self):
        return u"%s - %s" % (self.request.opis,self.status)

    def _gen_md5(self):
        return generate_md5(self.control, self.t_id, self.amount, self.request.email, self.t_status)

    def _check_md5(self):
        return bool(self._gen_md5() == self.md5)
    
    def save(self,*args, **kwargs):
        self.request = DotRequest.objects.get(control=self.control)
        if self._check_md5():

            super(DotResponse, self).save(*args, **kwargs)
            if self.t_status == '2': #WYKONANA
                dot_wykonana.send(sender=self)
            elif self.t_status == '1': #NOWA
                dot_nowa.send(sender=self)
            elif self.t_status == '3': #ODMOWA
                dot_odmowa.send(sender=self)
            elif self.t_status == '4': #ANULOWANA
                dot_anulowana.send(sender=self)
            elif self.t_status == '5': #REKLAMACJA
                dot_reklamacja.send(sender=self)
            else:
                dot_error.send(sender=self)
                raise BaseException("STATUS Not implemented:"+str(self.t_status))
        else:
            dot_error.send(sender=self)
            raise BaseException("MD5 INCORRECT: "+self.md5+" != "+self._gen_md5())