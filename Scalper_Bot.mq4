//+------------------------------------------------------------------+
//|                                               Scalper_Bot.mq4    |
//|             Disciplined, risk-first MT4 EA (H1 confluence)       |
//+------------------------------------------------------------------+
#property copyright ""
#property version   "1.0"
#property strict

// ---- Inputs ----
input double Risk_Per_Trade_Pct      = 0.5;    // % equity per trade
input double Daily_Profit_Cap_Pct    = 1.0;    // stop trading if reached
input double Daily_Loss_Limit_Pct    = 1.0;    // stop trading if reached
input double Max_Drawdown_Pct        = 15.0;   // hard kill-switch
input int    Max_Trades_Per_Day      = 12;
input int    Max_Concurrent_Trades   = 2;
input int    Scan_Interval_Seconds   = 10;

input int    RSI_Period              = 14;
input int    MACD_Fast               = 12;
input int    MACD_Slow               = 26;
input int    MACD_Signal             = 9;
input int    ATR_Period              = 14;

input int    EMA_Slope_Period        = 50;
input int    EMA_Slope_Lookback      = 5;
input double EMA_Slope_Threshold     = 5.0;   // pips over lookback

input double Min_SL_Pips             = 10.0;
input double Max_SL_Pips             = 25.0;
input double Min_TP_Pips             = 12.0;
input double Max_TP_Pips             = 35.0;
input double Min_RR                  = 1.2;

input double Max_Spread_Pips_Metals  = 20.0;
input double Max_Spread_Pips_FX      = 2.0;
input double ATR_Min_Pips            = 4.0;
input double ATR_Max_Pips            = 200.0;
input int    ATR_Regime_Period       = 20;

input bool   Trade_London_Session    = true;
input bool   Trade_NY_Session        = true;
input int    London_Start_Hour       = 7;  // Dublin time (UTC+0/+1)
input int    London_End_Hour         = 11;
input int    NY_Start_Hour           = 12;
input int    NY_End_Hour             = 16;

input bool   Reduce_Asian_Risk        = true;
input double Asian_Risk_Multiplier    = 0.5;

input int    Confidence_Threshold_Metals = 64;
input int    Confidence_Threshold_FX     = 60;
input double Entry_RSI_Buy_Max           = 48.0;
input double Entry_RSI_Sell_Min          = 52.0;
input double Entry_SR_Max_Distance_Pips  = 30.0;
input bool   Entry_Require_MACD_Align    = true;
input bool   Entry_Require_Trend_Direction = true;

// Allocation multipliers (per symbol)
input double Risk_Multiplier_XAU      = 1.0;  // 50% portfolio focus
input double Risk_Multiplier_XAG      = 0.7;  // 20% portfolio focus
input double Risk_Multiplier_FX       = 0.6;  // 30% portfolio focus

// Symbol enable toggles
input bool Enable_XAUUSD = true;
input bool Enable_XAGUSD = true;
input bool Enable_EURUSD = false;
input bool Enable_GBPUSD = false;
input bool Enable_USDJPY = false;

// Allowed symbols (trade only chart symbol, but whitelist input)
input string Allowed_Symbols          = "XAUUSD,EURUSD,GBPUSD,USDJPY";

// Very selective mode
enum TradeMode { CONSERVATIVE=0, BALANCED=1, ACTIVE=2 };
input TradeMode Mode = BALANCED;

// Telegram notifications
input bool   Telegram_Enable          = false;
input string Telegram_Bot_Token       = "";
input string Telegram_Chat_ID         = "";
input bool   Telegram_Test_OnInit     = true;
input int    Telegram_Min_IntervalSec = 30;

// Trade management (optional)
input bool   Enable_Trade_Management   = true;
input double BE_Trigger_RR             = 1.0;   // move SL to BE at >= this RR
input double BE_Offset_Pips            = 1.0;   // lock small profit at BE
input bool   Enable_Partial_Close      = true;
input double Partial_Close_RR          = 1.0;   // partial at >= this RR
input double Partial_Close_Percent     = 50.0;  // % volume to close
input bool   Enable_Trailing           = true;
input double Trail_Start_RR            = 1.5;   // start trailing at >= this RR
input double Trail_Step_Pips           = 10.0;  // trail step (pips)
input bool   Enable_Quick_Profit_Exit  = true;  // do not let good trades roundtrip
input double Quick_Profit_Close_RR     = 1.0;
input bool   Quick_Profit_Require_Rejection = true;
input bool   Enable_Time_Exit          = true;  // scalper timeout
input int    Max_Hold_Minutes          = 180;

// Support/Resistance caching (H1)
input int    SR_Lookback_Bars          = 200;
input int    SR_Pivot_Left             = 2;
input int    SR_Pivot_Right            = 2;
input int    SR_Max_Zones              = 5;
input double SR_Zone_Width_ATR_Mult    = 0.25; // zone half-width as ATR fraction

// Magic number
input int    Magic_Number              = 240131;

// ---- Globals ----
datetime g_last_h1_bar_time = 0;
int g_trades_today = 0;
int g_trades_today_metals = 0;
int g_trades_today_fx = 0;
int g_last_day_key = 0;

double g_day_start_equity = 0.0;
double g_peak_equity = 0.0;

datetime g_last_loss_time = 0;
int g_session_losses = 0;
datetime g_session_lock_until = 0;

int g_last_score = 0;
string g_last_regime = "UNKNOWN";
string g_last_lock_reason = "";
datetime g_last_telegram_time = 0;

// Logging
string LOG_DECISIONS = "Scalper_Decisions.csv";
string LOG_TRADES = "Scalper_Trades.csv";
string LOG_EVAL = "Scalper_Log.csv";

// S/R cache (per-chart symbol)
struct SRZone { double price; double half_width; bool is_resistance; datetime t; };
SRZone g_zones[20];
int    g_zone_count = 0;
datetime g_last_sr_update = 0;

// Closed-trade tracking (for loss cooldown/lockout)
int g_last_history_total = 0;

// ---- Helpers ----
double PipSize(const string symbol)
{
   double point = MarketInfo(symbol, MODE_POINT);
   int digits = (int)MarketInfo(symbol, MODE_DIGITS);
   if(digits == 3 || digits == 5) return point * 10.0;
   return point;
}

bool SymbolEnabled()
{
   string sym = _Symbol;
   if(StringFind(sym, "XAU") >= 0) return Enable_XAUUSD;
   if(StringFind(sym, "XAG") >= 0) return Enable_XAGUSD;
   if(StringFind(sym, "EURUSD") >= 0) return Enable_EURUSD;
   if(StringFind(sym, "GBPUSD") >= 0) return Enable_GBPUSD;
   if(StringFind(sym, "USDJPY") >= 0) return Enable_USDJPY;
   return false;
}

bool SymbolInWhitelist()
{
   string sym = StringUpper(_Symbol);
   string list = StringUpper(Allowed_Symbols);
   list = StringReplace(list, " ", "");
   int p = 0;
   while(true)
   {
      int comma = StringFind(list, ",", p);
      string token = (comma == -1) ? StringSubstr(list, p) : StringSubstr(list, p, comma - p);
      if(token == sym) return true;
      if(comma == -1) break;
      p = comma + 1;
   }
   return false;
}

string UrlEncode(const string text)
{
   string out = "";
   for(int i=0; i<StringLen(text); i++)
   {
      ushort c = StringGetCharacter(text, i);
      if((c>='a' && c<='z') || (c>='A' && c<='Z') || (c>='0' && c<='9') || c=='-' || c=='_' || c=='.')
         out += (string)CharToString((uchar)c);
      else if(c==' ') out += "%20";
      else
         out += StringFormat("%%%02X", c);
   }
   return out;
}

bool TelegramSend(const string msg)
{
   if(!Telegram_Enable) return false;
   if(Telegram_Bot_Token == "" || Telegram_Chat_ID == "") return false;
   if(TimeCurrent() - g_last_telegram_time < Telegram_Min_IntervalSec) return false;

   string url = "https://api.telegram.org/bot" + Telegram_Bot_Token + "/sendMessage";
   string body = "chat_id=" + Telegram_Chat_ID + "&text=" + UrlEncode(msg);
   char post[];
   StringToCharArray(body, post);
   char result[];
   string headers;
   int timeout = 5000;
   int code = WebRequest("POST", url, "application/x-www-form-urlencoded", timeout, post, result, headers);
   if(code == -1) return false;
   g_last_telegram_time = TimeCurrent();
   return true;
}

double GetSpreadInPips(const string symbol)
{
   double ask = MarketInfo(symbol, MODE_ASK);
   double bid = MarketInfo(symbol, MODE_BID);
   return (ask - bid) / PipSize(symbol);
}

bool IsMetals()
{
   return (StringFind(_Symbol, "XAU") >= 0 || StringFind(_Symbol, "XAG") >= 0);
}

bool IsNewBar(ENUM_TIMEFRAMES tf)
{
   datetime t = iTime(_Symbol, tf, 1);
   if(t == 0) return false;
   if(t != g_last_h1_bar_time)
   {
      g_last_h1_bar_time = t;
      return true;
   }
   return false;
}

bool IsInSession()
{
   MqlDateTime tm; TimeToStruct(TimeCurrent(), tm);
   int hour = tm.hour;
   bool london = Trade_London_Session && (hour >= London_Start_Hour && hour <= London_End_Hour);
   bool ny = Trade_NY_Session && (hour >= NY_Start_Hour && hour <= NY_End_Hour);
   return (london || ny);
}

bool IsAsianSession()
{
   MqlDateTime tm; TimeToStruct(TimeCurrent(), tm);
   int hour = tm.hour;
   return (hour >= 0 && hour < 6);
}

bool IsSpreadOK()
{
   double spread = GetSpreadInPips(_Symbol);
   if(IsMetals()) return spread <= Max_Spread_Pips_Metals;
   return spread <= Max_Spread_Pips_FX;
}

bool AtrOk(double atr_pips)
{
   return (atr_pips >= ATR_Min_Pips && atr_pips <= ATR_Max_Pips);
}

int PositionsDirectionCount(const string symbol, int direction)
{
   int count = 0;
   for(int i=OrdersTotal()-1; i>=0; i--)
   {
      if(!OrderSelect(i, SELECT_BY_POS, MODE_TRADES)) continue;
      if(OrderSymbol() != symbol) continue;
      if(OrderMagicNumber() != Magic_Number) continue;
      if(OrderType() == direction) count++;
   }
   return count;
}

bool DailyLimitsHit()
{
   double equity = AccountEquity();
   double pnl_pct = (equity - g_day_start_equity) / g_day_start_equity * 100.0;
   if(pnl_pct >= Daily_Profit_Cap_Pct) return true;
   if(pnl_pct <= -Daily_Loss_Limit_Pct) return true;
   return false;
}

bool DrawdownHit()
{
   double equity = AccountEquity();
   if(equity > g_peak_equity) g_peak_equity = equity;
   double dd = (g_peak_equity - equity) / g_peak_equity * 100.0;
   return dd >= Max_Drawdown_Pct;
}

void UpdateDailyCounters()
{
   MqlDateTime tm; TimeToStruct(TimeCurrent(), tm);
   int today = tm.year*10000 + tm.mon*100 + tm.day;
   if(today != g_last_day_key)
   {
      g_last_day_key = today;
      g_trades_today = 0;
      g_trades_today_metals = 0;
      g_trades_today_fx = 0;
      g_session_losses = 0;
      g_session_lock_until = 0;
      g_day_start_equity = AccountEquity();
      g_peak_equity = g_day_start_equity;
   }
}

bool RejectionCandle(bool buy)
{
   double o1 = iOpen(_Symbol, PERIOD_H1, 1);
   double c1 = iClose(_Symbol, PERIOD_H1, 1);
   double h1 = iHigh(_Symbol, PERIOD_H1, 1);
   double l1 = iLow(_Symbol, PERIOD_H1, 1);
   double body = MathAbs(c1 - o1);
   double upper_wick = h1 - MathMax(o1, c1);
   double lower_wick = MathMin(o1, c1) - l1;
   if(buy) return (lower_wick > body * 2.0 && c1 > o1);
   return (upper_wick > body * 2.0 && c1 < o1);
}

bool IsTrendRegime(double ema_slope_pips)
{
   return MathAbs(ema_slope_pips) >= EMA_Slope_Threshold;
}

bool IsLowVolRegime(double atr_pips, double atr_sma_pips)
{
   return atr_pips < atr_sma_pips * 0.7;
}

struct ScoreBreakdown
{
   int rsi;
   int macd;
   int sr;
   int candle;
   int atr;
   int total;
};

ScoreBreakdown EmptyScore()
{
   ScoreBreakdown e;
   e.rsi = 0; e.macd = 0; e.sr = 0; e.candle = 0; e.atr = 0; e.total = 0;
   return e;
}

ScoreBreakdown GetSetupScore(bool buy, double rsi, double macd_main, double macd_signal, double atr_pips, double dist_sr_pips, bool rejection)
{
   ScoreBreakdown s;
   s.rsi = 0; s.macd = 0; s.sr = 0; s.candle = 0; s.atr = 0; s.total = 0;

   if(buy && rsi <= Entry_RSI_Buy_Max) s.rsi = 20;
   if(!buy && rsi >= Entry_RSI_Sell_Min) s.rsi = 20;

   if((buy && macd_main > macd_signal) || (!buy && macd_main < macd_signal)) s.macd = 20;

   if(dist_sr_pips <= (Entry_SR_Max_Distance_Pips * 0.5)) s.sr = 20;
   else if(dist_sr_pips <= Entry_SR_Max_Distance_Pips) s.sr = 10;

   if(rejection) s.candle = 20;

   if(atr_pips >= ATR_Min_Pips && atr_pips <= ATR_Max_Pips) s.atr = 20;

   s.total = s.rsi + s.macd + s.sr + s.candle + s.atr;
   return s;
}

bool IsTradeAllowed()
{
   if(!SymbolInWhitelist()) { g_last_lock_reason = "SYMBOL_NOT_ALLOWED"; return false; }
   if(!SymbolEnabled()) { g_last_lock_reason = "SYMBOL_DISABLED"; return false; }
   if(DailyLimitsHit()) { g_last_lock_reason = "DAILY_LIMIT"; return false; }
   if(DrawdownHit()) { g_last_lock_reason = "DRAWDOWN"; return false; }
   if(!IsInSession()) { g_last_lock_reason = "OUT_OF_SESSION"; return false; }
   if(!IsSpreadOK()) { g_last_lock_reason = "SPREAD_TOO_HIGH"; return false; }
   if(OrdersTotal() >= Max_Concurrent_Trades) { g_last_lock_reason = "MAX_CONCURRENT"; return false; }
   if(g_session_lock_until > TimeCurrent()) { g_last_lock_reason = "SESSION_LOCK"; return false; }

   if(IsMetals())
   {
      if(g_trades_today_metals >= 6) { g_last_lock_reason = "METALS_LIMIT"; return false; }
   }
   else
   {
      if(g_trades_today_fx >= 5) { g_last_lock_reason = "FX_LIMIT"; return false; }
   }
   if(g_trades_today >= Max_Trades_Per_Day) { g_last_lock_reason = "DAILY_LIMIT"; return false; }
   if(g_last_loss_time > 0 && (TimeCurrent() - g_last_loss_time) < 900) { g_last_lock_reason = "LOSS_COOLDOWN"; return false; }

   return true;
}

// Tick-based risk sizing
double CalculateLotByRisk(double entry, double sl, double risk_pct)
{
   double equity = AccountEquity();
   double risk_amount = equity * (risk_pct / 100.0);

   double tick_size = MarketInfo(_Symbol, MODE_TICKSIZE);
   double tick_value = MarketInfo(_Symbol, MODE_TICKVALUE);
   double min_lot = MarketInfo(_Symbol, MODE_MINLOT);
   double max_lot = MarketInfo(_Symbol, MODE_MAXLOT);
   double step = MarketInfo(_Symbol, MODE_LOTSTEP);

   double sl_dist = MathAbs(entry - sl);
   if(tick_size <= 0 || tick_value <= 0 || sl_dist <= 0) return 0.0;

   double ticks_to_sl = sl_dist / tick_size;
   double loss_per_lot = ticks_to_sl * tick_value;
   if(loss_per_lot <= 0) return 0.0;

   double raw_lot = risk_amount / loss_per_lot;
   if(raw_lot < min_lot) return 0.0;

   double lot = MathMin(raw_lot, max_lot);
   lot = MathFloor(lot / step) * step;
   if(lot < min_lot) return 0.0;
   return lot;
}

void LogLine(const string file, const string line)
{
   int handle = FileOpen(file, FILE_READ|FILE_WRITE|FILE_TXT|FILE_ANSI);
   if(handle == INVALID_HANDLE) return;
   FileSeek(handle, 0, SEEK_END);
   FileWriteString(handle, line + "\r\n");
   FileClose(handle);
}

void EnsureLogHeader(const string file, const string header)
{
   int handle = FileOpen(file, FILE_READ|FILE_WRITE|FILE_TXT|FILE_ANSI);
   if(handle == INVALID_HANDLE) return;
   if(FileSize(handle) == 0) FileWriteString(handle, header + "\r\n");
   FileClose(handle);
}

void LogDecisionCSV(const string action, const ScoreBreakdown &s, double spread_pips, double atr_pips, double ema_slope)
{
   EnsureLogHeader(LOG_DECISIONS, "time,symbol,regime,score,total_rsi,macd,sr,candle,atr,spread,ema_slope,lock_reason,action");
   string line = StringFormat("%s,%s,%s,%d,%d,%d,%d,%d,%d,%.2f,%.2f,%s,%s",
      TimeToString(TimeCurrent(), TIME_DATE|TIME_SECONDS), _Symbol, g_last_regime,
      s.total, s.rsi, s.macd, s.sr, s.candle, s.atr,
      spread_pips, ema_slope, g_last_lock_reason, action);
   LogLine(LOG_DECISIONS, line);
}

void LogTradeCSV(const string side, double lot, double entry, double sl, double tp, const ScoreBreakdown &s)
{
   EnsureLogHeader(LOG_TRADES, "time,symbol,side,lot,entry,sl,tp,score");
   string line = StringFormat("%s,%s,%s,%.2f,%.5f,%.5f,%.5f,%d",
      TimeToString(TimeCurrent(), TIME_DATE|TIME_SECONDS), _Symbol, side, lot, entry, sl, tp, s.total);
   LogLine(LOG_TRADES, line);
}

void UpdateSRCache()
{
   datetime t = iTime(_Symbol, PERIOD_H1, 0);
   if(t==0 || t==g_last_sr_update) return;
   g_last_sr_update = t;

   double atr = iATR(_Symbol, PERIOD_H1, ATR_Period, 1);
   double half_width = atr * SR_Zone_Width_ATR_Mult;

   g_zone_count = 0;
   int L = MathMax(1, SR_Pivot_Left);
   int R = MathMax(1, SR_Pivot_Right);
   int maxbars = MathMin(SR_Lookback_Bars, 1000);

   int max_zones = MathMin(SR_Max_Zones, 10);
   for(int i=maxbars; i>=R+L+2 && g_zone_count<max_zones*2; i--)
   {
      double hi = iHigh(_Symbol, PERIOD_H1, i);
      double lo = iLow(_Symbol, PERIOD_H1, i);
      bool pivotHigh=true, pivotLow=true;

      for(int k=1;k<=L;k++){ if(iHigh(_Symbol, PERIOD_H1, i+k) >= hi) pivotHigh=false; if(iLow(_Symbol, PERIOD_H1, i+k) <= lo) pivotLow=false; }
      for(int k=1;k<=R;k++){ if(iHigh(_Symbol, PERIOD_H1, i-k) >  hi) pivotHigh=false; if(iLow(_Symbol, PERIOD_H1, i-k) <  lo) pivotLow=false; }

      if(pivotHigh && g_zone_count < 20)
      {
         g_zones[g_zone_count].price = hi;
         g_zones[g_zone_count].half_width = half_width;
         g_zones[g_zone_count].is_resistance = true;
         g_zones[g_zone_count].t = iTime(_Symbol, PERIOD_H1, i);
         g_zone_count++;
      }
      if(pivotLow && g_zone_count < 20)
      {
         g_zones[g_zone_count].price = lo;
         g_zones[g_zone_count].half_width = half_width;
         g_zones[g_zone_count].is_resistance = false;
         g_zones[g_zone_count].t = iTime(_Symbol, PERIOD_H1, i);
         g_zone_count++;
      }
   }
}

double NearestSRDistancePips(bool buy, double price)
{
   if(g_zone_count<=0) return 9999.0;
   double best = 999999.0;
   double pip = PipSize(_Symbol);
   for(int i=0;i<g_zone_count;i++)
   {
      if(buy && g_zones[i].is_resistance) continue;
      if(!buy && !g_zones[i].is_resistance) continue;

      double d = MathAbs(price - g_zones[i].price);
      if(d <= g_zones[i].half_width) return 0.0;
      if(d < best) best = d;
   }
   return best / pip;
}

double ClampToStep(double vol, double step)
{
   if(step<=0) return vol;
   return MathFloor(vol/step)*step;
}

void ManageOpenPositions()
{
   if(!Enable_Trade_Management) return;

   for(int i=OrdersTotal()-1; i>=0; i--)
   {
      if(!OrderSelect(i, SELECT_BY_POS, MODE_TRADES)) continue;
      if(OrderSymbol() != _Symbol) continue;
      if(OrderMagicNumber() != Magic_Number) continue;

      int type = OrderType();
      if(type != OP_BUY && type != OP_SELL) continue;

      double entry = OrderOpenPrice();
      double sl = OrderStopLoss();
      double tp = OrderTakeProfit();
      double vol = OrderLots();

      double bid = MarketInfo(_Symbol, MODE_BID);
      double ask = MarketInfo(_Symbol, MODE_ASK);
      double price = (type==OP_BUY) ? bid : ask;
      datetime opened_at = OrderOpenTime();

      double risk_dist = MathAbs(entry - sl);
      if(risk_dist <= 0) continue;

      double rr = (type==OP_BUY) ? (price-entry)/risk_dist : (entry-price)/risk_dist;

      if(Enable_Time_Exit && Max_Hold_Minutes > 0 && (TimeCurrent() - opened_at) >= (Max_Hold_Minutes * 60))
      {
         OrderClose(OrderTicket(), vol, price, 10, clrNONE);
         continue;
      }

      if(Enable_Quick_Profit_Exit && rr >= Quick_Profit_Close_RR)
      {
         bool close_now = true;
         if(Quick_Profit_Require_Rejection)
            close_now = (type == OP_BUY) ? RejectionCandle(false) : RejectionCandle(true);
         if(close_now)
         {
            OrderClose(OrderTicket(), vol, price, 10, clrNONE);
            continue;
         }
      }

      // Partial close
      if(Enable_Partial_Close && rr >= Partial_Close_RR)
      {
         int ticket = OrderTicket();
         string gv = "MR_PART_"+IntegerToString(ticket);
         if(!GlobalVariableCheck(gv))
         {
            double minv = MarketInfo(_Symbol, MODE_MINLOT);
            double step = MarketInfo(_Symbol, MODE_LOTSTEP);
            double close_vol = vol * (Partial_Close_Percent/100.0);
            close_vol = ClampToStep(close_vol, step);
            if(close_vol >= minv && close_vol < vol)
            {
               bool ok = OrderClose(ticket, close_vol, price, 10, clrNONE);
               if(ok) GlobalVariableSet(gv, 1.0);
            }
         }
      }

      // Move to breakeven
      if(rr >= BE_Trigger_RR)
      {
         double new_sl = sl;
         double pip = PipSize(_Symbol);
         if(type==OP_BUY) new_sl = entry + BE_Offset_Pips*pip;
         else new_sl = entry - BE_Offset_Pips*pip;

         if((type==OP_BUY && (sl==0 || new_sl>sl)) || (type==OP_SELL && (sl==0 || new_sl<sl)))
         {
            OrderModify(OrderTicket(), entry, new_sl, tp, 0, clrNONE);
         }
      }

      // Trailing stop
      if(Enable_Trailing && rr >= Trail_Start_RR)
      {
         double pip = PipSize(_Symbol);
         double step = Trail_Step_Pips*pip;
         double new_sl = sl;

         if(type==OP_BUY)
         {
            double candidate = price - step;
            if(candidate > new_sl) new_sl = candidate;
            if(new_sl > sl) OrderModify(OrderTicket(), entry, new_sl, tp, 0, clrNONE);
         }
         else
         {
            double candidate = price + step;
            if(candidate < new_sl || new_sl==0) new_sl = candidate;
            if(new_sl < sl || sl==0) OrderModify(OrderTicket(), entry, new_sl, tp, 0, clrNONE);
         }
      }
   }
}

void TrackClosedTrades()
{
   int total = OrdersHistoryTotal();
   if(total == g_last_history_total) return;
   g_last_history_total = total;

   for(int i=total-1; i>=0; i--)
   {
      if(!OrderSelect(i, SELECT_BY_POS, MODE_HISTORY)) continue;
      if(OrderSymbol() != _Symbol) continue;
      if(OrderMagicNumber() != Magic_Number) continue;
      if(OrderCloseTime() == 0) continue;

      double profit = OrderProfit() + OrderSwap() + OrderCommission();
      if(profit < 0)
      {
         g_last_loss_time = TimeCurrent();
         g_session_losses++;
         if(g_session_losses >= 2)
         {
            g_session_lock_until = TimeCurrent() + 6 * 3600;
         }
      }
      break;
   }
}

void Evaluate()
{
   UpdateDailyCounters();
   g_last_lock_reason = "";

   UpdateSRCache();
   if(!IsNewBar(PERIOD_H1)) return;

   if(!IsTradeAllowed())
   {
      LogDecisionCSV("SKIP", EmptyScore(), GetSpreadInPips(_Symbol), 0.0, 0.0);
      return;
   }

   double rsi = iRSI(_Symbol, PERIOD_H1, RSI_Period, PRICE_CLOSE, 1);
   double macd_main = iMACD(_Symbol, PERIOD_H1, MACD_Fast, MACD_Slow, MACD_Signal, PRICE_CLOSE, MODE_MAIN, 1);
   double macd_signal = iMACD(_Symbol, PERIOD_H1, MACD_Fast, MACD_Slow, MACD_Signal, PRICE_CLOSE, MODE_SIGNAL, 1);
   double atr = iATR(_Symbol, PERIOD_H1, ATR_Period, 1);

   double atr_sma = 0.0;
   for(int i=1; i<=ATR_Regime_Period; i++)
      atr_sma += iATR(_Symbol, PERIOD_H1, ATR_Period, i);
   atr_sma /= ATR_Regime_Period;

   double atr_pips = atr / PipSize(_Symbol);
   if(!AtrOk(atr_pips)) { g_last_lock_reason = "ATR_RANGE"; LogDecisionCSV("SKIP", EmptyScore(), GetSpreadInPips(_Symbol), atr_pips, 0.0); return; }

   double ema_now = iMA(_Symbol, PERIOD_H1, EMA_Slope_Period, 0, MODE_EMA, PRICE_CLOSE, 1);
   double ema_prev = iMA(_Symbol, PERIOD_H1, EMA_Slope_Period, 0, MODE_EMA, PRICE_CLOSE, 1 + EMA_Slope_Lookback);
   double ema_slope_pips = (ema_now - ema_prev) / PipSize(_Symbol);

   if(IsLowVolRegime(atr_pips, atr_sma / PipSize(_Symbol)))
   {
      g_last_regime = "LOW_VOL";
      g_last_lock_reason = "LOW_VOL";
      LogDecisionCSV("SKIP", EmptyScore(), GetSpreadInPips(_Symbol), atr_pips, ema_slope_pips);
      return;
   }
   g_last_regime = IsTrendRegime(ema_slope_pips) ? "TREND" : "RANGE";

   double bid = MarketInfo(_Symbol, MODE_BID);
   double ask = MarketInfo(_Symbol, MODE_ASK);

   double dist_support = NearestSRDistancePips(true, bid);
   double dist_resist  = NearestSRDistancePips(false, ask);
   bool buy_setup = (rsi <= Entry_RSI_Buy_Max && dist_support <= Entry_SR_Max_Distance_Pips);
   bool sell_setup = (rsi >= Entry_RSI_Sell_Min && dist_resist <= Entry_SR_Max_Distance_Pips);
   if(Entry_Require_MACD_Align)
   {
      buy_setup = buy_setup && (macd_main > macd_signal);
      sell_setup = sell_setup && (macd_main < macd_signal);
   }
   if(Entry_Require_Trend_Direction && g_last_regime == "TREND")
   {
      if(ema_slope_pips > 0.0) sell_setup = false;
      if(ema_slope_pips < 0.0) buy_setup = false;
   }
   if(!buy_setup && !sell_setup) { g_last_lock_reason = "NO_SETUP"; LogDecisionCSV("SKIP", EmptyScore(), GetSpreadInPips(_Symbol), atr_pips, ema_slope_pips); return; }

   bool buy_rej = RejectionCandle(true);
   bool sell_rej = RejectionCandle(false);

   ScoreBreakdown score_buy = buy_setup ? GetSetupScore(true, rsi, macd_main, macd_signal, atr_pips, dist_support, buy_rej) : EmptyScore();
   ScoreBreakdown score_sell = sell_setup ? GetSetupScore(false, rsi, macd_main, macd_signal, atr_pips, dist_resist, sell_rej) : EmptyScore();

   g_last_score = MathMax(score_buy.total, score_sell.total);

   int threshold = IsMetals() ? Confidence_Threshold_Metals : Confidence_Threshold_FX;
   bool buy = (score_buy.total >= threshold && score_buy.total >= score_sell.total);
   bool sell = (score_sell.total >= threshold && score_sell.total > score_buy.total);

   if(buy && PositionsDirectionCount(_Symbol, OP_BUY) > 0) { g_last_lock_reason = "STACK"; LogDecisionCSV("SKIP", score_buy, GetSpreadInPips(_Symbol), atr_pips, ema_slope_pips); return; }
   if(sell && PositionsDirectionCount(_Symbol, OP_SELL) > 0) { g_last_lock_reason = "STACK"; LogDecisionCSV("SKIP", score_sell, GetSpreadInPips(_Symbol), atr_pips, ema_slope_pips); return; }

   if(!(buy || sell)) { g_last_lock_reason = "SCORE"; LogDecisionCSV("SKIP", (buy_setup?score_buy:score_sell), GetSpreadInPips(_Symbol), atr_pips, ema_slope_pips); return; }

   // Selective caps
   if(IsMetals())
   {
      if(g_trades_today_metals >= 6) { g_last_lock_reason = "METALS_LIMIT"; LogDecisionCSV("SKIP", score_buy.total>score_sell.total?score_buy:score_sell, GetSpreadInPips(_Symbol), atr_pips, ema_slope_pips); return; }
   }
   else
   {
      if(g_trades_today_fx >= 5) { g_last_lock_reason = "FX_LIMIT"; LogDecisionCSV("SKIP", score_buy.total>score_sell.total?score_buy:score_sell, GetSpreadInPips(_Symbol), atr_pips, ema_slope_pips); return; }
   }
   if(g_trades_today >= Max_Trades_Per_Day) { g_last_lock_reason = "DAILY_LIMIT"; LogDecisionCSV("SKIP", score_buy.total>score_sell.total?score_buy:score_sell, GetSpreadInPips(_Symbol), atr_pips, ema_slope_pips); return; }
   if(g_last_loss_time > 0 && (TimeCurrent() - g_last_loss_time) < 900) { g_last_lock_reason = "LOSS_COOLDOWN"; LogDecisionCSV("SKIP", score_buy.total>score_sell.total?score_buy:score_sell, GetSpreadInPips(_Symbol), atr_pips, ema_slope_pips); return; }

   double sl_pips = MathMax(Min_SL_Pips, MathMin(Max_SL_Pips, atr_pips * 1.2));
   double tp_pips = MathMax(Min_TP_Pips, MathMin(Max_TP_Pips, sl_pips * Min_RR));

   double sl = buy ? (bid - sl_pips * PipSize(_Symbol)) : (ask + sl_pips * PipSize(_Symbol));
   double tp = buy ? (bid + tp_pips * PipSize(_Symbol)) : (ask - tp_pips * PipSize(_Symbol));

   double risk_pct = Risk_Per_Trade_Pct;
   if(StringFind(_Symbol, "XAU") >= 0) risk_pct *= Risk_Multiplier_XAU;
   else if(StringFind(_Symbol, "XAG") >= 0) risk_pct *= Risk_Multiplier_XAG;
   else risk_pct *= Risk_Multiplier_FX;

   if(Reduce_Asian_Risk && IsAsianSession())
      risk_pct *= Asian_Risk_Multiplier;

   double entry = buy ? ask : bid;
   double lot = CalculateLotByRisk(entry, sl, risk_pct);
   if(lot <= 0) { g_last_lock_reason = "LOT_ZERO"; return; }

   int ticket = -1;
   int slip = 10;
   if(buy) ticket = OrderSend(_Symbol, OP_BUY, lot, ask, slip, sl, tp, "Scalper", Magic_Number, 0, clrBlue);
   if(sell) ticket = OrderSend(_Symbol, OP_SELL, lot, bid, slip, sl, tp, "Scalper", Magic_Number, 0, clrRed);

   if(ticket > 0)
   {
      g_trades_today++;
      if(IsMetals()) g_trades_today_metals++; else g_trades_today_fx++;
      LogTradeCSV(buy ? "BUY" : "SELL", lot, entry, sl, tp, buy ? score_buy : score_sell);
      LogDecisionCSV(buy ? "BUY" : "SELL", buy ? score_buy : score_sell, GetSpreadInPips(_Symbol), atr_pips, ema_slope_pips);
      TelegramSend(StringFormat("Scalper %s %s | Score %d | SL %.5f TP %.5f", _Symbol, buy ? "BUY" : "SELL", g_last_score, sl, tp));
   }
   else
   {
      g_last_lock_reason = "ORDER_FAIL";
      LogDecisionCSV("SKIP", buy ? score_buy : score_sell, GetSpreadInPips(_Symbol), atr_pips, ema_slope_pips);
   }
}

void UpdateDashboard()
{
   double equity = AccountEquity();
   double pnl_pct = (equity - g_day_start_equity) / g_day_start_equity * 100.0;
   double dd_pct = (g_peak_equity > 0) ? (g_peak_equity - equity) / g_peak_equity * 100.0 : 0.0;

   string risk_mode = "Normal";
   if(DailyLimitsHit()) risk_mode = "Locked";
   else if(IsAsianSession() && Reduce_Asian_Risk) risk_mode = "Reduced";

   Comment(
      "Scalper | ", _Symbol, "\n",
      "Daily PnL: ", DoubleToString(pnl_pct, 2), "%\n",
      "Drawdown: ", DoubleToString(dd_pct, 2), "%\n",
      "Active Trades: ", OrdersTotal(), "\n",
      "Trades Today: ", g_trades_today, "\n",
      "Session: ", (IsInSession() ? "ON" : "OFF"), "\n",
      "Risk Mode: ", risk_mode, "\n",
      "Regime: ", g_last_regime, "\n",
      "Last Score: ", g_last_score, "\n",
      "Lock: ", g_last_lock_reason
   );
}

int OnInit()
{
   g_day_start_equity = AccountEquity();
   g_peak_equity = g_day_start_equity;
   g_last_history_total = OrdersHistoryTotal();

   if(Telegram_Test_OnInit && Telegram_Enable)
      TelegramSend("Scalper EA started on " + _Symbol);

   EventSetTimer(Scan_Interval_Seconds);
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   EventKillTimer();
}

void OnTimer()
{
   TrackClosedTrades();
   ManageOpenPositions();
   Evaluate();
   UpdateDashboard();
}

void OnTick()
{
   // no-op: logic runs on timer
}
