import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ScreenerService } from '../../services/screener.service';
import { Stock } from '../../models/stock.model';

@Component({
  selector: 'app-stock-list',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './stock-list.component.html',
  styleUrls: ['./stock-list.component.css']
})
export class StockListComponent implements OnInit {
  stocks: Stock[] = [];
  loading = true;
  error = false;

  constructor(private screenerService: ScreenerService) {}

  ngOnInit(): void {
    this.screenerService.getCurrentStocks().subscribe({
      next: (data) => {
        this.stocks = data;
        this.loading = false;
      },
      error: () => {
        this.error = true;
        this.loading = false;
      }
    });
  }

  getTradingViewUrl(stock: Stock): string {
    return `https://www.tradingview.com/chart/?symbol=${stock.exchange}:${stock.symbol}`;
  }

  hasValidExchange(stock: Stock): boolean {
    return !!stock.exchange && stock.exchange.trim().length > 0;
  }
}

