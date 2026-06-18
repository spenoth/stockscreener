import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ScreenerService } from '../../services/screener.service';
import { Stock } from '../../models/stock.model';

type NotificationState = 'success' | 'error' | null;

@Component({
  selector: 'app-stock-list',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './stock-list.component.html',
  styleUrls: ['./stock-list.component.css']
})
export class StockListComponent implements OnInit {
  stocks: Stock[] = [];
  loading = true;
  error = false;

  // Dialog state
  dialogOpen = false;
  dialogSymbol = '';
  selectedTimeframe = '1w';
  readonly timeframes = [
    { value: '1h', label: '1 Hour' },
    { value: '1w', label: '1 Week' },
  ];

  // Request state
  loadingPrices = false;
  notification: NotificationState = null;
  notificationMessage = '';

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

  openDialog(stock: Stock): void {
    this.dialogSymbol = stock.symbol;
    this.selectedTimeframe = '1w';
    this.notification = null;
    this.notificationMessage = '';
    this.dialogOpen = true;
  }

  closeDialog(): void {
    if (this.loadingPrices) return;
    this.dialogOpen = false;
  }

  submitLoad(): void {
    this.loadingPrices = true;
    this.notification = null;
    this.screenerService.loadHistoricalPrices(this.dialogSymbol, this.selectedTimeframe).subscribe({
      next: (res) => {
        this.loadingPrices = false;
        this.notification = 'success';
        this.notificationMessage = `Successfully inserted ${res.inserted} bar(s) for ${res.symbol} [${res.timeframe}].`;
      },
      error: () => {
        this.loadingPrices = false;
        this.notification = 'error';
        this.notificationMessage = `Failed to load prices for ${this.dialogSymbol}. Please try again.`;
      }
    });
  }
}


