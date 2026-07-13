import { Component } from '@angular/core';
import { StockListComponent } from './components/stock-list/stock-list.component';
import { BmsbSupertrendComponent } from './components/bmsb-supertrend/bmsb-supertrend.component';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [StockListComponent, BmsbSupertrendComponent],
  template: `
    <div class="app-container">
      <h1>Stock Screener</h1>
      <app-stock-list></app-stock-list>
      <app-bmsb-supertrend></app-bmsb-supertrend>
    </div>
  `,
  styles: [`
    .app-container {
      max-width: 900px;
      margin: 0 auto;
      padding: 20px;
    }
    h1 {
      color: #333;
      border-bottom: 2px solid #1976d2;
      padding-bottom: 10px;
    }
  `]
})
export class AppComponent {}

