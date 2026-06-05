import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { Stock } from '../models/stock.model';
import { environment } from '../../environments/environment';

@Injectable({
  providedIn: 'root'
})
export class ScreenerService {
  private readonly apiUrl = `${environment.apiBaseUrl}/api/screener/bmsb/current`;

  constructor(private http: HttpClient) {}

  getCurrentStocks(): Observable<Stock[]> {
    return this.http.get<Stock[]>(this.apiUrl);
  }
}

