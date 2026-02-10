//+------------------------------------------------------------------+
//|                                               Mad_Rabbit_Bot.mq5 |
//|               Disciplined, risk-first MT5 EA (H1 confluence)     |
//+------------------------------------------------------------------+
#property copyright ""
#property version   "1.1"
#property strict

#include <Trade/Trade.mqh>

CTrade trade;

// ---- Inputs ----
input double Risk_Per_Trade_Pct      = 0.5;    // % equity per trade
input double Daily_Profit_Cap_Pct    = 1.0;    // stop trading if reached
input double Daily_Loss_Limit_Pct    = 1.0;    // stop trading if reached
input double Max_Drawdown_Pct        = 15.0;   // hard kill-switch
input int    Max_Trades_Per_Day      = 20;
input int    Max_Concurrent_Trades   = 6;
input int    Scan_Interval_Seconds   = 10;

input int    RSI_Period              = 14;
input int    MACD_Fast               = 12;
input int    MACD_Slow               = 26;
input int    MACD_Signal             = 9;
input int    ATR_Period              = 14;

input int    EMA_Slope_Period        = 50;
input int    EMA_Slope_Lookback      = 5;
input double EMA_Slope_Threshold     = 5.0;   // pips over lookback
input ENUM_TIMEFRAMES Analysis_Timeframe = PERIOD_M30;

input double Min_SL_Pips             = 30.0;
input double Max_SL_Pips             = 40.0;
input double Min_TP_Pips             = 60.0;
input double Max_TP_Pips             = 80.0;
input double Min_RR                  = 2.0;

input double Max_Spread_Pips_Metals  = 35.0;
input double Max_Spread_Pips_FX      = 2.0;
input double ATR_Min_Pips            = 10.0;
input double ATR_Max_Pips            = 200.0;
input int    ATR_Regime_Period       = 20;
input bool   Enable_Adaptive_Filters = true;
input int    Adaptive_ATR_Lookback_Bars = 120;
input double Adaptive_ATR_Min_Percentile = 20.0;
input double Adaptive_ATR_Max_Percentile = 90.0;
input int    Adaptive_Spread_Lookback = 120;
input double Adaptive_Spread_Max_Mult = 1.5;

input bool   Trade_London_Session    = true;
input bool   Trade_NY_Session        = true;
input int    London_Start_Hour       = 7;  // Dublin time (UTC+0/+1)
input int    London_End_Hour         = 11;
input int    NY_Start_Hour           = 12;
input int    NY_End_Hour             = 16;

input bool   Reduce_Asian_Risk        = true;
input double Asian_Risk_Multiplier    = 0.5;

input int    Confidence_Threshold_Metals = 75;
input int    Confidence_Threshold_FX     = 70;
input bool   Enable_DD_Throttle      = true;
input double DD_Throttle_Start_Pct   = 2.0;
input double DD_Throttle_Full_Pct    = 8.0;
input int    DD_Threshold_Bump_Max   = 12;

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
input string Allowed_Symbols = "XAUUSD,EURUSD,GBPUSD,USDJPY";

// Very selective mode
enum TradeMode { CONSERVATIVE=0, BALANCED=1, ACTIVE=2 };
input TradeMode Mode = CONSERVATIVE;

// Telegram notifications
input bool   Telegram_Enable          = false;
input string Telegram_Bot_Token       = "";
input string Telegram_Chat_ID         = "";
input bool   Telegram_Test_OnInit     = true;
input int    Telegram_Min_IntervalSec = 30;

// AI signal bridge (HTTP polling)
input bool   Enable_AI_Signals        = false;
input bool   AI_Use_Only_Mode         = true;
enum AIProvider { AI_PROVIDER_RELAY=0, AI_PROVIDER_OPENAI=1 };
input AIProvider AI_Provider          = AI_PROVIDER_OPENAI;
input string AI_Endpoint              = "https://api.openai.com/v1/chat/completions";
input string AI_API_Key               = "";
input string AI_OpenAI_URL            = "https://api.openai.com/v1/chat/completions";
input string AI_OpenAI_Model          = "gpt-4o-mini";
input string AI_OpenAI_System_Prompt  = "You are a cautious trading signal engine. Return strict JSON only with keys: id,symbol,signal,confidence,sl,tp,expires_unix,reason.";
input int    AI_Poll_Seconds          = 300;   // 5 minutes
input int    AI_HTTP_Timeout_Ms       = 5000;
input int    AI_Min_Confidence        = 70;
input int    AI_Signal_TTL_Seconds    = 900;   // fallback TTL if API does not send expiry
input bool   Enable_AI_Advisory       = true;
input double AI_Advisory_Weight       = 0.35;
input int    AI_Advisory_Opposite_Penalty = 12;


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

// Support/Resistance caching (analysis timeframe)
input int    SR_Lookback_Bars          = 200;
input int    SR_Pivot_Left            = 2;
input int    SR_Pivot_Right           = 2;
input int    SR_Max_Zones             = 5;
input double SR_Zone_Width_ATR_Mult   = 0.25; // zone half-width as ATR fraction
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
datetime g_last_ai_poll_time = 0;
string g_last_ai_signal_id = "";
string g_last_ai_executed_id = "";
string g_last_ai_signal = "NONE";
double g_last_ai_confidence = 0.0;
string g_last_ai_reason = "";
string g_last_ai_status = "DISABLED";
bool g_ai_advisory_ready = false;
string g_ai_advisory_id = "";
string g_ai_advisory_signal = "NONE";
double g_ai_advisory_confidence = 0.0;
double g_ai_advisory_sl = 0.0;
double g_ai_advisory_tp = 0.0;
datetime g_ai_advisory_expires = 0;
string g_ai_advisory_reason = "";
double g_dynamic_atr_min = 0.0;
double g_dynamic_atr_max = 0.0;
double g_dynamic_spread_max = 0.0;
double g_spread_hist[];

struct ScoreBreakdown
{
   int rsi;
   int macd;
   int sr;
   int candle;
   int atr;
   int total;
};

struct AISignal
{
   bool valid;
   string id;
   string symbol;
   string signal;
   double confidence;
   double sl;
   double tp;
   datetime expires_time;
   string reason;
};

int rsi_handle = INVALID_HANDLE;
int macd_handle = INVALID_HANDLE;
int atr_handle = INVALID_HANDLE;
int ema_handle = INVALID_HANDLE;

// Logging
string LOG_DECISIONS = "MadRabbit_Decisions.csv";
string LOG_TRADES = "MadRabbit_Trades.csv";
string LOG_EVAL = "MadRabbit_Log.csv";

// ---- Helpers ----
double PipSize(const string symbol)
{
   double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
   int digits = (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS);
   if(digits == 3 || digits == 5) return point * 10.0;
   return point;
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

string ToUpperCopy(const string text)
{
   string out = "";
   for(int i=0; i<StringLen(text); i++)
   {
      ushort c = StringGetCharacter(text, i);
      if(c >= 'a' && c <= 'z') c = c - 32;
      out += (string)CharToString((uchar)c);
   }
   return out;
}

string RemoveSpacesCopy(const string text)
{
   string out = "";
   for(int i=0; i<StringLen(text); i++)
   {
      ushort c = StringGetCharacter(text, i);
      if(c != ' ') out += (string)CharToString((uchar)c);
   }
   return out;
}

string TimeframeTag(const ENUM_TIMEFRAMES tf)
{
   if(tf == PERIOD_M1) return "M1";
   if(tf == PERIOD_M5) return "M5";
   if(tf == PERIOD_M15) return "M15";
   if(tf == PERIOD_M30) return "M30";
   if(tf == PERIOD_H1) return "H1";
   if(tf == PERIOD_H4) return "H4";
   if(tf == PERIOD_D1) return "D1";
   string t = EnumToString(tf);
   StringReplace(t, "PERIOD_", "");
   return t;
}

string TrimCopy(const string text)
{
   int start = 0;
   int end = StringLen(text) - 1;
   while(start <= end)
   {
      ushort c = StringGetCharacter(text, start);
      if(c == ' ' || c == '\t' || c == '\r' || c == '\n') start++;
      else break;
   }
   while(end >= start)
   {
      ushort c = StringGetCharacter(text, end);
      if(c == ' ' || c == '\t' || c == '\r' || c == '\n') end--;
      else break;
   }
   if(end < start) return "";
   return StringSubstr(text, start, end - start + 1);
}

string EscapeJson(const string text)
{
   string out = "";
   for(int i = 0; i < StringLen(text); i++)
   {
      ushort c = StringGetCharacter(text, i);
      if(c == '\\') out += "\\\\";
      else if(c == '\"') out += "\\\"";
      else if(c == '\n') out += "\\n";
      else if(c == '\r') out += "\\r";
      else if(c == '\t') out += "\\t";
      else out += (string)CharToString((uchar)c);
   }
   return out;
}

string CompactForLog(const string text, const int maxLen)
{
   string out = text;
   StringReplace(out, "\r", " ");
   StringReplace(out, "\n", " ");
   out = TrimCopy(out);
   if(maxLen > 0 && StringLen(out) > maxLen) out = StringSubstr(out, 0, maxLen);
   return out;
}

bool JsonGetStringValue(const string json, const string key, string &value)
{
   string pattern = "\"" + key + "\"";
   int k = StringFind(json, pattern);
   if(k < 0) return false;
   int c = StringFind(json, ":", k + StringLen(pattern));
   if(c < 0) return false;
   int q1 = StringFind(json, "\"", c + 1);
   if(q1 < 0) return false;
   string out = "";
   bool escaped = false;
   for(int i = q1 + 1; i < StringLen(json); i++)
   {
      ushort ch = StringGetCharacter(json, i);
      if(escaped)
      {
         if(ch == 'n') out += "\n";
         else if(ch == 'r') out += "\r";
         else if(ch == 't') out += "\t";
         else out += (string)CharToString((uchar)ch);
         escaped = false;
         continue;
      }
      if(ch == '\\')
      {
         escaped = true;
         continue;
      }
      if(ch == '\"')
      {
         value = out;
         return true;
      }
      out += (string)CharToString((uchar)ch);
   }
   return false;
}

bool JsonGetNumberValue(const string json, const string key, double &value)
{
   string pattern = "\"" + key + "\"";
   int k = StringFind(json, pattern);
   if(k < 0) return false;
   int c = StringFind(json, ":", k + StringLen(pattern));
   if(c < 0) return false;
   int s = c + 1;
   while(s < StringLen(json))
   {
      ushort ch = StringGetCharacter(json, s);
      if(ch == ' ' || ch == '\t' || ch == '\r' || ch == '\n') s++;
      else break;
   }
   int e = s;
   while(e < StringLen(json))
   {
      ushort ch = StringGetCharacter(json, e);
      if(ch == ',' || ch == '}' || ch == ' ' || ch == '\r' || ch == '\n' || ch == '\t') break;
      e++;
   }
   if(e <= s) return false;
   string raw = TrimCopy(StringSubstr(json, s, e - s));
   if(raw == "") return false;
   value = StringToDouble(raw);
   return true;
}

AISignal EmptyAISignal()
{
   AISignal s;
   s.valid = false;
   s.id = "";
   s.symbol = "";
   s.signal = "NO_TRADE";
   s.confidence = 0.0;
   s.sl = 0.0;
   s.tp = 0.0;
   s.expires_time = 0;
   s.reason = "";
   return s;
}

string ExtractJsonObject(const string text)
{
   int start = StringFind(text, "{");
   if(start < 0) return text;
   int end = -1;
   for(int i = StringLen(text) - 1; i >= 0; i--)
   {
      if(StringGetCharacter(text, i) == '}')
      {
         end = i;
         break;
      }
   }
   if(end <= start) return text;
   return StringSubstr(text, start, end - start + 1);
}

double ClampDouble(const double value, const double min_value, const double max_value)
{
   if(value < min_value) return min_value;
   if(value > max_value) return max_value;
   return value;
}

double CurrentDrawdownPct()
{
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   if(equity > g_peak_equity) g_peak_equity = equity;
   if(g_peak_equity <= 0.0) return 0.0;
   return (g_peak_equity - equity) / g_peak_equity * 100.0;
}

double PercentileFromArray(const double &src[], const int count, const double pct)
{
   if(count <= 0) return 0.0;
   double sorted[];
   ArrayResize(sorted, count);
   for(int i = 0; i < count; i++) sorted[i] = src[i];
   ArraySort(sorted);

   double p = ClampDouble(pct, 0.0, 100.0) / 100.0;
   double pos = (count - 1) * p;
   int lo = (int)MathFloor(pos);
   int hi = (int)MathCeil(pos);
   if(lo == hi) return sorted[lo];
   double weight = pos - lo;
   return sorted[lo] + (sorted[hi] - sorted[lo]) * weight;
}

void RecordSpreadSample()
{
   double spread = GetSpreadInPips(_Symbol);
   if(spread <= 0.0) return;
   int n = ArraySize(g_spread_hist);
   if(n < Adaptive_Spread_Lookback)
   {
      ArrayResize(g_spread_hist, n + 1);
      g_spread_hist[n] = spread;
      return;
   }
   for(int i = 1; i < n; i++) g_spread_hist[i - 1] = g_spread_hist[i];
   g_spread_hist[n - 1] = spread;
}

void RefreshAdaptiveLimits()
{
   g_dynamic_spread_max = IsMetals() ? Max_Spread_Pips_Metals : Max_Spread_Pips_FX;
   g_dynamic_atr_min = ATR_Min_Pips;
   g_dynamic_atr_max = ATR_Max_Pips;
   if(!Enable_Adaptive_Filters) return;

   RecordSpreadSample();
   int sCount = ArraySize(g_spread_hist);
   if(sCount >= 20)
   {
      double p75 = PercentileFromArray(g_spread_hist, sCount, 75.0);
      g_dynamic_spread_max = MathMax(g_dynamic_spread_max, p75 * Adaptive_Spread_Max_Mult);
   }

   if(atr_handle == INVALID_HANDLE) return;
   int lookback = MathMin(MathMax(Adaptive_ATR_Lookback_Bars, 20), 500);
   double atr_raw[];
   ArrayResize(atr_raw, lookback);
   int got = CopyBuffer(atr_handle, 0, 1, lookback, atr_raw);
   if(got < 20) return;

   double atr_pips_hist[];
   ArrayResize(atr_pips_hist, got);
   double pip = PipSize(_Symbol);
   if(pip <= 0.0) return;
   for(int i = 0; i < got; i++) atr_pips_hist[i] = atr_raw[i] / pip;

   double pLow = PercentileFromArray(atr_pips_hist, got, Adaptive_ATR_Min_Percentile);
   double pHigh = PercentileFromArray(atr_pips_hist, got, Adaptive_ATR_Max_Percentile);
   g_dynamic_atr_min = MathMax(0.1, MathMin(ATR_Min_Pips, pLow));
   g_dynamic_atr_max = MathMax(ATR_Max_Pips, pHigh);
   if(g_dynamic_atr_min >= g_dynamic_atr_max)
   {
      g_dynamic_atr_min = ATR_Min_Pips;
      g_dynamic_atr_max = ATR_Max_Pips;
   }
}

int DynamicThresholdBump()
{
   if(!Enable_DD_Throttle) return 0;
   double dd = CurrentDrawdownPct();
   if(dd <= DD_Throttle_Start_Pct) return 0;
   double full = MathMax(DD_Throttle_Full_Pct, DD_Throttle_Start_Pct + 0.1);
   double ratio = ClampDouble((dd - DD_Throttle_Start_Pct) / (full - DD_Throttle_Start_Pct), 0.0, 1.0);
   int ddBump = (int)MathRound(ratio * DD_Threshold_Bump_Max);
   int lossBump = MathMin(6, g_session_losses * 2);
   return ddBump + lossBump;
}

int DynamicScoreThreshold(const int base)
{
   return base + DynamicThresholdBump();
}

int DynamicAIMinConfidence()
{
   return DynamicScoreThreshold(AI_Min_Confidence);
}

double RiskThrottleMultiplier()
{
   if(!Enable_DD_Throttle) return 1.0;
   double dd = CurrentDrawdownPct();
   if(dd <= DD_Throttle_Start_Pct) return 1.0;
   double full = MathMax(DD_Throttle_Full_Pct, DD_Throttle_Start_Pct + 0.1);
   double ratio = ClampDouble((dd - DD_Throttle_Start_Pct) / (full - DD_Throttle_Start_Pct), 0.0, 1.0);
   // reduce risk linearly down to 50% under stress
   return 1.0 - (0.5 * ratio);
}

bool ParseAISignalFromJson(const string raw, datetime now, AISignal &sig)
{
   string rawSignal = "";
   string rawId = "";
   string rawSymbol = "";
   string rawReason = "";
   double confidence = 0.0;
   double sl = 0.0;
   double tp = 0.0;
   double expires_unix = 0.0;

   string body = ExtractJsonObject(raw);
   if(!JsonGetStringValue(body, "signal", rawSignal))
   {
      g_last_ai_status = "PARSE_SIGNAL_FAIL";
      return false;
   }
   JsonGetStringValue(body, "id", rawId);
   JsonGetStringValue(body, "symbol", rawSymbol);
   JsonGetStringValue(body, "reason", rawReason);
   JsonGetNumberValue(body, "confidence", confidence);
   JsonGetNumberValue(body, "sl", sl);
   JsonGetNumberValue(body, "tp", tp);
   JsonGetNumberValue(body, "expires_unix", expires_unix);

   string signal = ToUpperCopy(TrimCopy(rawSignal));
   string symbol = (rawSymbol == "") ? _Symbol : rawSymbol;
   string id = (rawId == "") ? IntegerToString((int)now) + "_" + signal : rawId;

   g_last_ai_signal = signal;
   g_last_ai_signal_id = id;
   g_last_ai_confidence = confidence;
   g_last_ai_reason = rawReason;

   if(signal == "NO_TRADE")
   {
      g_last_ai_status = "AI_NO_TRADE";
      return false;
   }
   if(signal != "BUY" && signal != "SELL")
   {
      g_last_ai_status = "BAD_SIGNAL";
      return false;
   }
   if(ToUpperCopy(symbol) != ToUpperCopy(_Symbol))
   {
      g_last_ai_status = "SYMBOL_MISMATCH";
      return false;
   }
   if(confidence < DynamicAIMinConfidence())
   {
      g_last_ai_status = "LOW_CONFIDENCE";
      return false;
   }

   datetime expiry = now + AI_Signal_TTL_Seconds;
   if(expires_unix > 0) expiry = (datetime)((long)expires_unix);

   sig.valid = true;
   sig.id = id;
   sig.symbol = symbol;
   sig.signal = signal;
   sig.confidence = confidence;
   sig.sl = sl;
   sig.tp = tp;
   sig.expires_time = expiry;
   sig.reason = rawReason;
   g_last_ai_status = "OK";
   return true;
}

bool IsOpenAIEndpoint(const string endpoint)
{
   string u = ToUpperCopy(TrimCopy(endpoint));
   if(u == "") return false;
   return (StringFind(u, "API.OPENAI.COM") >= 0 || StringFind(u, "/CHAT/COMPLETIONS") >= 0);
}

bool PollAISignal(AISignal &sig, double atr_pips, double ema_slope_pips)
{
   sig = EmptyAISignal();
   g_last_ai_reason = "";
   if(!Enable_AI_Signals)
   {
      g_last_ai_status = "DISABLED";
      return false;
   }
   if(AI_API_Key == "")
   {
      g_last_ai_status = "NO_API_KEY";
      return false;
   }

   datetime now = TimeCurrent();
   if(g_last_ai_poll_time > 0 && (now - g_last_ai_poll_time) < AI_Poll_Seconds)
   {
      g_last_ai_status = "WAIT_POLL_WINDOW";
      return false;
   }
   g_last_ai_poll_time = now;

   AIProvider provider = AI_Provider;
   string endpoint = TrimCopy(AI_Endpoint);
   if(endpoint == "" && AI_OpenAI_URL != "")
   {
      endpoint = TrimCopy(AI_OpenAI_URL);
      provider = AI_PROVIDER_OPENAI;
   }
   if(endpoint == "")
   {
      g_last_ai_status = "NO_ENDPOINT";
      return false;
   }
   bool useOpenAI = (provider == AI_PROVIDER_OPENAI || IsOpenAIEndpoint(endpoint));

   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double spread = GetSpreadInPips(_Symbol);
   string payload = "";
   string headers = "Content-Type: application/json\r\n";
   if(useOpenAI)
   {
      headers += "Authorization: Bearer " + AI_API_Key + "\r\n";
      string userPrompt = StringFormat(
         "Return one decision in strict JSON only. symbol=%s time=%s timeframe=%s bid=%.8f ask=%.8f spread_pips=%.2f atr_pips=%.2f ema_slope_pips=%.2f. If no opportunity set signal=NO_TRADE.",
         _Symbol,
         TimeToString(now, TIME_DATE|TIME_SECONDS),
         TimeframeTag(Analysis_Timeframe),
         bid,
         ask,
         spread,
         atr_pips,
         ema_slope_pips
      );
      payload =
         "{\"model\":\"" + EscapeJson(AI_OpenAI_Model) + "\","
         "\"temperature\":0,"
         "\"messages\":["
         "{\"role\":\"system\",\"content\":\"" + EscapeJson(AI_OpenAI_System_Prompt) + "\"},"
         "{\"role\":\"user\",\"content\":\"" + EscapeJson(userPrompt) + "\"}"
         "]}";
   }
   else
   {
      headers += "X-API-Key: " + AI_API_Key + "\r\n";
      payload = StringFormat(
         "{\"symbol\":\"%s\",\"time\":\"%s\",\"timeframe\":\"%s\",\"bid\":%.8f,\"ask\":%.8f,\"spread_pips\":%.2f,\"atr_pips\":%.2f,\"ema_slope_pips\":%.2f}",
         _Symbol,
         TimeToString(now, TIME_DATE|TIME_SECONDS),
         TimeframeTag(Analysis_Timeframe),
         bid,
         ask,
         spread,
         atr_pips,
         ema_slope_pips
      );
   }

   char post[];
   char result[];
   int payloadBytes = StringToCharArray(payload, post, 0, WHOLE_ARRAY, CP_UTF8);
   if(payloadBytes <= 1)
   {
      g_last_ai_status = "PAYLOAD_ENCODE_FAIL";
      return false;
   }
   ArrayResize(post, payloadBytes - 1); // drop terminating \0
   string response_headers = "";
   ResetLastError();
   int code = WebRequest("POST", endpoint, headers, AI_HTTP_Timeout_Ms, post, result, response_headers);
   if(code == -1)
   {
      g_last_ai_status = "HTTP_ERR_" + IntegerToString(GetLastError());
      g_last_ai_reason = "WEBREQUEST_FAIL";
      return false;
   }
   string body = CharArrayToString(result, 0, -1, CP_UTF8);
   if(code < 200 || code >= 300)
   {
      g_last_ai_status = "HTTP_" + IntegerToString(code);
      g_last_ai_reason = CompactForLog(body, 220);
      return false;
   }
   if(body == "")
   {
      g_last_ai_status = "EMPTY_BODY";
      g_last_ai_reason = "EMPTY_RESPONSE";
      return false;
   }

   if(useOpenAI)
   {
      string content = "";
      if(!JsonGetStringValue(body, "content", content))
      {
         g_last_ai_status = "PARSE_CONTENT_FAIL";
         g_last_ai_reason = CompactForLog(body, 220);
         return false;
      }
      return ParseAISignalFromJson(content, now, sig);
   }
   return ParseAISignalFromJson(body, now, sig);
}

void RefreshAIAdvisoryCache()
{
   if(!(Enable_AI_Signals && !AI_Use_Only_Mode && Enable_AI_Advisory)) return;
   if(AI_API_Key == "") return;
   if(atr_handle == INVALID_HANDLE || ema_handle == INVALID_HANDLE) return;

   double atr_buff[2];
   double ema_buff[10];
   if(CopyBuffer(atr_handle, 0, 0, 2, atr_buff) < 2) return;
   if(CopyBuffer(ema_handle, 0, 0, EMA_Slope_Lookback + 1, ema_buff) < EMA_Slope_Lookback + 1) return;

   double pip = PipSize(_Symbol);
   if(pip <= 0.0) return;
   double atr_pips = atr_buff[1] / pip;
   double ema_slope_pips = (ema_buff[1] - ema_buff[EMA_Slope_Lookback]) / pip;

   AISignal ai;
   bool got = PollAISignal(ai, atr_pips, ema_slope_pips);
   if(!got || !ai.valid) return;

   g_ai_advisory_ready = true;
   g_ai_advisory_id = ai.id;
   g_ai_advisory_signal = ai.signal;
   g_ai_advisory_confidence = ai.confidence;
   g_ai_advisory_sl = ai.sl;
   g_ai_advisory_tp = ai.tp;
   g_ai_advisory_expires = ai.expires_time;
   g_ai_advisory_reason = ai.reason;
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
   double ask = SymbolInfoDouble(symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(symbol, SYMBOL_BID);
   return (ask - bid) / PipSize(symbol);
}

bool IsMetals()
{
   return (StringFind(_Symbol, "XAU") >= 0 || StringFind(_Symbol, "XAG") >= 0);
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
   string sym = ToUpperCopy(_Symbol);
   string list = RemoveSpacesCopy(ToUpperCopy(Allowed_Symbols));
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
   double maxSpread = g_dynamic_spread_max;
   if(maxSpread <= 0.0) maxSpread = IsMetals() ? Max_Spread_Pips_Metals : Max_Spread_Pips_FX;
   return spread <= maxSpread;
}

bool AtrOk(double atr_pips)
{
   double minAtr = g_dynamic_atr_min > 0.0 ? g_dynamic_atr_min : ATR_Min_Pips;
   double maxAtr = g_dynamic_atr_max > 0.0 ? g_dynamic_atr_max : ATR_Max_Pips;
   return (atr_pips >= minAtr && atr_pips <= maxAtr);
}

int PositionsDirectionCount(const string symbol, long direction)
{
   int count = 0;
   for(int i=0; i<PositionsTotal(); i++)
   {
      if(PositionGetSymbol(i) != symbol) continue;
      if(PositionGetInteger(POSITION_TYPE) == direction) count++;
   }
   return count;
}

bool DailyLimitsHit()
{
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   double pnl_pct = (equity - g_day_start_equity) / g_day_start_equity * 100.0;
   if(pnl_pct >= Daily_Profit_Cap_Pct) return true;
   if(pnl_pct <= -Daily_Loss_Limit_Pct) return true;
   return false;
}

bool DrawdownHit()
{
   double dd = CurrentDrawdownPct();
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
      g_day_start_equity = AccountInfoDouble(ACCOUNT_EQUITY);
      g_peak_equity = g_day_start_equity;
   }
}

// Simple S/R from recent swings (non-repainting)
void GetRecentSwings(int lookback, double &swing_high, double &swing_low)
{
   swing_high = -DBL_MAX;
   swing_low = DBL_MAX;
   for(int i=2; i<=lookback; i++)
   {
      double high = iHigh(_Symbol, Analysis_Timeframe, i);
      double low = iLow(_Symbol, Analysis_Timeframe, i);
      if(high > swing_high) swing_high = high;
      if(low < swing_low) swing_low = low;
   }
}

bool RejectionCandle(bool buy)
{
   double o1 = iOpen(_Symbol, Analysis_Timeframe, 1);
   double c1 = iClose(_Symbol, Analysis_Timeframe, 1);
   double h1 = iHigh(_Symbol, Analysis_Timeframe, 1);
   double l1 = iLow(_Symbol, Analysis_Timeframe, 1);
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

// --- S/R cache (per-chart symbol) ---
struct SRZone { double price; double half_width; bool is_resistance; datetime t; };
SRZone g_zones[20];
int    g_zone_count = 0;
datetime g_last_sr_update = 0;

// --- Trade management helpers ---
ulong  g_magic = 240131; // Mad Rabbit magic number

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

   if(buy && rsi < 35) s.rsi = 20;
   if(!buy && rsi > 65) s.rsi = 20;

   if((buy && macd_main > macd_signal) || (!buy && macd_main < macd_signal)) s.macd = 20;

   if(dist_sr_pips <= 10.0) s.sr = 20;
   else if(dist_sr_pips <= 20.0) s.sr = 10;

   if(rejection) s.candle = 20;

   double minAtr = g_dynamic_atr_min > 0.0 ? g_dynamic_atr_min : ATR_Min_Pips;
   double maxAtr = g_dynamic_atr_max > 0.0 ? g_dynamic_atr_max : ATR_Max_Pips;
   if(atr_pips >= minAtr && atr_pips <= maxAtr) s.atr = 20;

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
   if(PositionsTotal() >= Max_Concurrent_Trades) { g_last_lock_reason = "MAX_CONCURRENT"; return false; }
   if(g_session_lock_until > TimeCurrent()) { g_last_lock_reason = "SESSION_LOCK"; return false; }

   if(IsMetals())
   {
      if(g_trades_today_metals >= 3) { g_last_lock_reason = "METALS_LIMIT"; return false; }
   }
   else
   {
      if(g_trades_today_fx >= 2) { g_last_lock_reason = "FX_LIMIT"; return false; }
   }
   if(g_trades_today >= Max_Trades_Per_Day) { g_last_lock_reason = "DAILY_LIMIT"; return false; }
   if(g_last_loss_time > 0 && (TimeCurrent() - g_last_loss_time) < 1800) { g_last_lock_reason = "LOSS_COOLDOWN"; return false; }

   return true;
}

// Tick-based risk sizing
double CalculateLotByRisk(double entry, double sl, double risk_pct)
{
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   double risk_amount = equity * (risk_pct / 100.0);

   double tick_size = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double tick_value = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double min_lot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double max_lot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);

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
   EnsureLogHeader(LOG_DECISIONS, "time,symbol,regime,score,total_rsi,macd,sr,candle,atr,spread,ema_slope,lock_reason,action,ai_id,ai_signal,ai_confidence,ai_status,ai_reason");
   string aiReasonCsv = g_last_ai_reason;
   StringReplace(aiReasonCsv, ",", ";");
   StringReplace(aiReasonCsv, "\r", " ");
   StringReplace(aiReasonCsv, "\n", " ");
   string line = StringFormat("%s,%s,%s,%d,%d,%d,%d,%d,%d,%.2f,%.2f,%s,%s,%s,%s,%.2f,%s,%s",
      TimeToString(TimeCurrent(), TIME_DATE|TIME_SECONDS), _Symbol, g_last_regime,
      s.total, s.rsi, s.macd, s.sr, s.candle, s.atr,
      spread_pips, ema_slope, g_last_lock_reason, action,
      g_last_ai_signal_id, g_last_ai_signal, g_last_ai_confidence, g_last_ai_status, aiReasonCsv);
   LogLine(LOG_DECISIONS, line);
}

void LogTradeCSV(const string side, double lot, double entry, double sl, double tp, const ScoreBreakdown &s)
{
   EnsureLogHeader(LOG_TRADES, "time,symbol,side,lot,entry,sl,tp,score");
   string line = StringFormat("%s,%s,%s,%.2f,%.5f,%.5f,%.5f,%d",
      TimeToString(TimeCurrent(), TIME_DATE|TIME_SECONDS), _Symbol, side, lot, entry, sl, tp, s.total);
   LogLine(LOG_TRADES, line);
}

// ---- Core Trading Logic ----
void UpdateSRCache()
{
   // Recompute zones only on new analysis timeframe bar
   datetime t=iTime(_Symbol, Analysis_Timeframe, 0);
   if(t==0 || t==g_last_sr_update) return;
   g_last_sr_update = t;

   // Need ATR for zone width
   double atr_arr[3];
   if(atr_handle==INVALID_HANDLE || CopyBuffer(atr_handle,0,1,1,atr_arr)<1) return;
   double atr = atr_arr[0];
   double half_width = atr * SR_Zone_Width_ATR_Mult;

   g_zone_count = 0;
   int L = MathMax(1, SR_Pivot_Left);
   int R = MathMax(1, SR_Pivot_Right);
   int maxbars = MathMin(SR_Lookback_Bars, 1000);

   // Scan from older to newer so newest zones end up last
   int max_zones = MathMin(SR_Max_Zones, 10);
   for(int i=maxbars; i>=R+L+2 && g_zone_count<max_zones*2; i--)
   {
      double hi = iHigh(_Symbol, Analysis_Timeframe, i);
      double lo = iLow(_Symbol, Analysis_Timeframe, i);
      bool pivotHigh=true, pivotLow=true;

      for(int k=1;k<=L;k++){ if(iHigh(_Symbol, Analysis_Timeframe, i+k) >= hi) pivotHigh=false; if(iLow(_Symbol, Analysis_Timeframe, i+k) <= lo) pivotLow=false; }
      for(int k=1;k<=R;k++){ if(iHigh(_Symbol, Analysis_Timeframe, i-k) >  hi) pivotHigh=false; if(iLow(_Symbol, Analysis_Timeframe, i-k) <  lo) pivotLow=false; }

      if(pivotHigh && g_zone_count < 20)
      {
         g_zones[g_zone_count].price = hi;
         g_zones[g_zone_count].half_width = half_width;
         g_zones[g_zone_count].is_resistance = true;
         g_zones[g_zone_count].t = iTime(_Symbol, Analysis_Timeframe, i);
         g_zone_count++;
      }
      if(pivotLow && g_zone_count < 20)
      {
         g_zones[g_zone_count].price = lo;
         g_zones[g_zone_count].half_width = half_width;
         g_zones[g_zone_count].is_resistance = false;
         g_zones[g_zone_count].t = iTime(_Symbol, Analysis_Timeframe, i);
         g_zone_count++;
      }
   }
}

double NearestSRDistancePips(bool buy, double price)
{
   // buy uses support distance, sell uses resistance distance
   if(g_zone_count<=0) return 9999.0;
   double best = 999999.0;
   double pip = PipSize(_Symbol);
   for(int i=0;i<g_zone_count;i++)
   {
      if(buy && g_zones[i].is_resistance) continue;
      if(!buy && !g_zones[i].is_resistance) continue;

      double d = MathAbs(price - g_zones[i].price);
      // if inside zone, treat as 0 distance
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

   for(int i=PositionsTotal()-1;i>=0;i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(!PositionSelectByTicket(ticket)) continue;

      string sym = PositionGetString(POSITION_SYMBOL);
      if(sym != _Symbol) continue;

      long magic = (long)PositionGetInteger(POSITION_MAGIC);
      if((ulong)magic != g_magic) continue;

      long type = PositionGetInteger(POSITION_TYPE);
      double entry = PositionGetDouble(POSITION_PRICE_OPEN);
      double sl = PositionGetDouble(POSITION_SL);
      double tp = PositionGetDouble(POSITION_TP);
      double vol = PositionGetDouble(POSITION_VOLUME);

      double bid = SymbolInfoDouble(sym, SYMBOL_BID);
      double ask = SymbolInfoDouble(sym, SYMBOL_ASK);
      double price = (type==POSITION_TYPE_BUY) ? bid : ask;

      double risk_dist = MathAbs(entry - sl);
      if(risk_dist <= 0) continue;

      double rr = (type==POSITION_TYPE_BUY) ? (price-entry)/risk_dist : (entry-price)/risk_dist;

      // Partial close
      if(Enable_Partial_Close && rr >= Partial_Close_RR)
      {
         // prevent multiple partial closes: mark by comment tag in position comment is not editable; use global var keyed by ticket
         ulong ticket = (ulong)PositionGetInteger(POSITION_TICKET);
         string gv = "MR_PART_"+(string)ticket;
         if(!GlobalVariableCheck(gv))
         {
            double minv = SymbolInfoDouble(sym, SYMBOL_VOLUME_MIN);
            double step = SymbolInfoDouble(sym, SYMBOL_VOLUME_STEP);
            double close_vol = vol * (Partial_Close_Percent/100.0);
            close_vol = ClampToStep(close_vol, step);
            if(close_vol >= minv && close_vol < vol)
            {
               trade.SetExpertMagicNumber(g_magic);
               trade.PositionClosePartial(ticket, close_vol);
               GlobalVariableSet(gv, 1.0);
            }
         }
      }

      // Move to breakeven
      if(rr >= BE_Trigger_RR)
      {
         double new_sl = sl;
         double pip = PipSize(sym);
         if(type==POSITION_TYPE_BUY) new_sl = entry + BE_Offset_Pips*pip;
         else new_sl = entry - BE_Offset_Pips*pip;

         // only tighten
         if((type==POSITION_TYPE_BUY && (sl==0 || new_sl>sl)) || (type==POSITION_TYPE_SELL && (sl==0 || new_sl<sl)))
         {
            trade.SetExpertMagicNumber(g_magic);
            trade.PositionModify(sym, new_sl, tp);
         }
      }

      // Trailing stop
      if(Enable_Trailing && rr >= Trail_Start_RR)
      {
         double pip = PipSize(sym);
         double step = Trail_Step_Pips*pip;
         double new_sl = sl;

         if(type==POSITION_TYPE_BUY)
         {
            double candidate = price - step;
            if(candidate > new_sl) new_sl = candidate;
            if(new_sl > sl) { trade.SetExpertMagicNumber(g_magic); trade.PositionModify(sym, new_sl, tp); }
         }
         else
         {
            double candidate = price + step;
            if(candidate < new_sl || new_sl==0) new_sl = candidate;
            if(new_sl < sl || sl==0) { trade.SetExpertMagicNumber(g_magic); trade.PositionModify(sym, new_sl, tp); }
         }
      }
   }
}

bool EvaluateAI()
{
   UpdateDailyCounters();
   g_last_lock_reason = "";

   UpdateSRCache();

   if(!IsTradeAllowed())
   {
      LogDecisionCSV("SKIP", EmptyScore(), GetSpreadInPips(_Symbol), 0.0, 0.0);
      return true;
   }

   if(rsi_handle == INVALID_HANDLE || macd_handle == INVALID_HANDLE || atr_handle == INVALID_HANDLE || ema_handle == INVALID_HANDLE)
   {
      g_last_lock_reason = "HANDLE_INVALID";
      LogDecisionCSV("SKIP", EmptyScore(), GetSpreadInPips(_Symbol), 0.0, 0.0);
      return true;
   }

   double atr_buff[2];
   double ema_buff[10];
   if(CopyBuffer(atr_handle, 0, 0, 2, atr_buff) < 2) return false;
   if(CopyBuffer(ema_handle, 0, 0, EMA_Slope_Lookback + 1, ema_buff) < EMA_Slope_Lookback + 1) return false;

   double atr_hist[];
   ArrayResize(atr_hist, ATR_Regime_Period + 2);
   if(CopyBuffer(atr_handle, 0, 1, ATR_Regime_Period + 1, atr_hist) < ATR_Regime_Period + 1) return false;
   double atr_sma = 0.0;
   for(int i = 0; i < ATR_Regime_Period; i++) atr_sma += atr_hist[i];
   atr_sma /= ATR_Regime_Period;

   double atr_pips = atr_buff[1] / PipSize(_Symbol);
   double ema_now = ema_buff[1];
   double ema_prev = ema_buff[EMA_Slope_Lookback];
   double ema_slope_pips = (ema_now - ema_prev) / PipSize(_Symbol);

   if(!AtrOk(atr_pips))
   {
      g_last_lock_reason = "ATR_RANGE";
      LogDecisionCSV("SKIP", EmptyScore(), GetSpreadInPips(_Symbol), atr_pips, ema_slope_pips);
      return true;
   }
   if(IsLowVolRegime(atr_pips, atr_sma / PipSize(_Symbol)))
   {
      g_last_regime = "LOW_VOL";
      g_last_lock_reason = "LOW_VOL";
      LogDecisionCSV("SKIP", EmptyScore(), GetSpreadInPips(_Symbol), atr_pips, ema_slope_pips);
      return true;
   }
   g_last_regime = IsTrendRegime(ema_slope_pips) ? "TREND" : "RANGE";

   AISignal ai;
   bool got = PollAISignal(ai, atr_pips, ema_slope_pips);
   if(!got)
   {
      if(g_last_ai_status == "WAIT_POLL_WINDOW") return false;
      g_last_lock_reason = g_last_ai_status;
      LogDecisionCSV("SKIP", EmptyScore(), GetSpreadInPips(_Symbol), atr_pips, ema_slope_pips);
      return false;
   }
   if(!ai.valid) return false;

   if(ai.expires_time > 0 && TimeCurrent() > ai.expires_time)
   {
      g_last_ai_status = "SIGNAL_EXPIRED";
      g_last_lock_reason = "SIGNAL_EXPIRED";
      LogDecisionCSV("SKIP", EmptyScore(), GetSpreadInPips(_Symbol), atr_pips, ema_slope_pips);
      return true;
   }
   if(ai.id == g_last_ai_executed_id)
   {
      g_last_ai_status = "DUPLICATE_SIGNAL";
      g_last_lock_reason = "DUPLICATE_SIGNAL";
      LogDecisionCSV("SKIP", EmptyScore(), GetSpreadInPips(_Symbol), atr_pips, ema_slope_pips);
      return true;
   }

   bool buy = (ai.signal == "BUY");
   bool sell = (ai.signal == "SELL");
   if(!buy && !sell)
   {
      g_last_ai_status = "UNSUPPORTED_SIGNAL";
      g_last_lock_reason = "UNSUPPORTED_SIGNAL";
      LogDecisionCSV("SKIP", EmptyScore(), GetSpreadInPips(_Symbol), atr_pips, ema_slope_pips);
      return true;
   }

   if(buy && PositionsDirectionCount(_Symbol, POSITION_TYPE_BUY) > 0)
   {
      g_last_lock_reason = "STACK";
      LogDecisionCSV("SKIP", EmptyScore(), GetSpreadInPips(_Symbol), atr_pips, ema_slope_pips);
      return true;
   }
   if(sell && PositionsDirectionCount(_Symbol, POSITION_TYPE_SELL) > 0)
   {
      g_last_lock_reason = "STACK";
      LogDecisionCSV("SKIP", EmptyScore(), GetSpreadInPips(_Symbol), atr_pips, ema_slope_pips);
      return true;
   }

   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double entry = buy ? ask : bid;

   double sl_pips = MathMax(Min_SL_Pips, MathMin(Max_SL_Pips, atr_pips * 1.2));
   double tp_pips = MathMax(Min_TP_Pips, MathMin(Max_TP_Pips, sl_pips * Min_RR));
   double fallback_sl = buy ? (bid - sl_pips * PipSize(_Symbol)) : (ask + sl_pips * PipSize(_Symbol));
   double fallback_tp = buy ? (bid + tp_pips * PipSize(_Symbol)) : (ask - tp_pips * PipSize(_Symbol));

   double sl = ai.sl > 0 ? ai.sl : fallback_sl;
   double tp = ai.tp > 0 ? ai.tp : fallback_tp;

   if(buy && (sl >= entry || tp <= entry))
   {
      sl = fallback_sl;
      tp = fallback_tp;
   }
   if(sell && (sl <= entry || tp >= entry))
   {
      sl = fallback_sl;
      tp = fallback_tp;
   }

   double rr = MathAbs(tp - entry) / MathAbs(entry - sl);
   if(rr < Min_RR)
   {
      g_last_ai_status = "RR_TOO_LOW";
      g_last_lock_reason = "RR_TOO_LOW";
      LogDecisionCSV("SKIP", EmptyScore(), GetSpreadInPips(_Symbol), atr_pips, ema_slope_pips);
      return true;
   }

   double risk_pct = Risk_Per_Trade_Pct;
   if(StringFind(_Symbol, "XAU") >= 0) risk_pct *= Risk_Multiplier_XAU;
   else if(StringFind(_Symbol, "XAG") >= 0) risk_pct *= Risk_Multiplier_XAG;
   else risk_pct *= Risk_Multiplier_FX;
   if(Reduce_Asian_Risk && IsAsianSession()) risk_pct *= Asian_Risk_Multiplier;
   risk_pct *= RiskThrottleMultiplier();

   double lot = CalculateLotByRisk(entry, sl, risk_pct);
   if(lot <= 0)
   {
      g_last_lock_reason = "LOT_ZERO";
      LogDecisionCSV("SKIP", EmptyScore(), GetSpreadInPips(_Symbol), atr_pips, ema_slope_pips);
      return true;
   }

   trade.SetExpertMagicNumber(g_magic);
   trade.SetDeviationInPoints(10);
   bool ok = false;
   if(buy) ok = trade.Buy(lot, _Symbol, ask, sl, tp, "MadRabbit_AI");
   if(sell) ok = trade.Sell(lot, _Symbol, bid, sl, tp, "MadRabbit_AI");

   ScoreBreakdown aiScore = EmptyScore();
   aiScore.total = (int)MathRound(ai.confidence);

   if(ok)
   {
      g_trades_today++;
      if(IsMetals()) g_trades_today_metals++; else g_trades_today_fx++;
      g_last_ai_executed_id = ai.id;
      g_last_score = aiScore.total;
      LogTradeCSV(buy ? "BUY" : "SELL", lot, entry, sl, tp, aiScore);
      LogDecisionCSV(buy ? "BUY" : "SELL", aiScore, GetSpreadInPips(_Symbol), atr_pips, ema_slope_pips);
      TelegramSend(StringFormat("Mad Rabbit AI %s %s | Conf %.1f | SL %.5f TP %.5f", _Symbol, buy ? "BUY" : "SELL", ai.confidence, sl, tp));
   }
   else
   {
      g_last_lock_reason = "ORDER_FAIL";
      LogDecisionCSV("SKIP", aiScore, GetSpreadInPips(_Symbol), atr_pips, ema_slope_pips);
   }
   return true;
}

void Evaluate()
{
   UpdateDailyCounters();
   g_last_lock_reason = "";


   UpdateSRCache();
   if(!IsNewBar(Analysis_Timeframe)) return;

   if(!IsTradeAllowed())
   {
      LogDecisionCSV("SKIP", EmptyScore(), GetSpreadInPips(_Symbol), 0.0, 0.0);
      return;
   }

   double rsi_buff[2];
   double macd_main[2];
   double macd_signal[2];
   double atr_buff[2];
   double ema_buff[10];

   if(rsi_handle == INVALID_HANDLE || macd_handle == INVALID_HANDLE || atr_handle == INVALID_HANDLE || ema_handle == INVALID_HANDLE)
   {
      g_last_lock_reason = "HANDLE_INVALID";
      LogDecisionCSV("SKIP", EmptyScore(), GetSpreadInPips(_Symbol), 0.0, 0.0);
      return;
   }

   if(CopyBuffer(rsi_handle, 0, 0, 2, rsi_buff) < 2) return;
   if(CopyBuffer(macd_handle, 0, 0, 2, macd_main) < 2) return;
   if(CopyBuffer(macd_handle, 1, 0, 2, macd_signal) < 2) return;
   if(CopyBuffer(atr_handle, 0, 0, 2, atr_buff) < 2) return;
   if(CopyBuffer(ema_handle, 0, 0, EMA_Slope_Lookback+1, ema_buff) < EMA_Slope_Lookback+1) return;

   
   // ATR regime baseline using buffered ATR values (no MQL4-style calls)
   double atr_hist[];
   ArrayResize(atr_hist, ATR_Regime_Period+2);
   if(CopyBuffer(atr_handle, 0, 1, ATR_Regime_Period+1, atr_hist) < ATR_Regime_Period+1) return;
   double atr_sma = 0.0;
   for(int i=0;i<ATR_Regime_Period;i++) atr_sma += atr_hist[i];
   atr_sma /= ATR_Regime_Period;


   double atr_pips = atr_buff[1] / PipSize(_Symbol);
   if(!AtrOk(atr_pips)) { g_last_lock_reason = "ATR_RANGE"; LogDecisionCSV("SKIP", EmptyScore(), GetSpreadInPips(_Symbol), atr_pips, 0.0); return; }

   double ema_now = ema_buff[1];
   double ema_prev = ema_buff[EMA_Slope_Lookback];
   double ema_slope_pips = (ema_now - ema_prev) / PipSize(_Symbol);

   if(IsLowVolRegime(atr_pips, atr_sma / PipSize(_Symbol)))
   {
      g_last_regime = "LOW_VOL";
      g_last_lock_reason = "LOW_VOL";
      LogDecisionCSV("SKIP", EmptyScore(), GetSpreadInPips(_Symbol), atr_pips, ema_slope_pips);
      return;
   }
   g_last_regime = IsTrendRegime(ema_slope_pips) ? "TREND" : "RANGE";
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);

   double dist_support = NearestSRDistancePips(true, bid);
   double dist_resist  = NearestSRDistancePips(false, ask);
   bool buy_setup = (rsi_buff[1] < 40 && dist_support <= 20);
   bool sell_setup = (rsi_buff[1] > 60 && dist_resist <= 20);
   if(!buy_setup && !sell_setup) { g_last_lock_reason = "NO_SETUP"; LogDecisionCSV("SKIP", EmptyScore(), GetSpreadInPips(_Symbol), atr_pips, ema_slope_pips); return; }

   bool buy_rej = RejectionCandle(true);
   bool sell_rej = RejectionCandle(false);

   ScoreBreakdown score_buy = buy_setup ? GetSetupScore(true, rsi_buff[1], macd_main[1], macd_signal[1], atr_pips, dist_support, buy_rej) : EmptyScore();
   ScoreBreakdown score_sell = sell_setup ? GetSetupScore(false, rsi_buff[1], macd_main[1], macd_signal[1], atr_pips, dist_resist, sell_rej) : EmptyScore();
   double buy_effective = score_buy.total;
   double sell_effective = score_sell.total;

   if(Enable_AI_Signals && Enable_AI_Advisory && AI_API_Key != "")
   {
      if(g_ai_advisory_ready && (g_ai_advisory_expires == 0 || TimeCurrent() <= g_ai_advisory_expires))
      {
         double w = ClampDouble(AI_Advisory_Weight, 0.0, 1.0);
         if(g_ai_advisory_signal == "BUY")
         {
            buy_effective = (1.0 - w) * buy_effective + w * g_ai_advisory_confidence;
            sell_effective = MathMax(0.0, sell_effective - AI_Advisory_Opposite_Penalty);
         }
         else if(g_ai_advisory_signal == "SELL")
         {
            sell_effective = (1.0 - w) * sell_effective + w * g_ai_advisory_confidence;
            buy_effective = MathMax(0.0, buy_effective - AI_Advisory_Opposite_Penalty);
         }
      }
      else if(g_ai_advisory_ready && g_ai_advisory_expires > 0 && TimeCurrent() > g_ai_advisory_expires)
      {
         g_ai_advisory_ready = false;
      }
   }

   g_last_score = (int)MathRound(MathMax(buy_effective, sell_effective));
   int baseThreshold = IsMetals() ? Confidence_Threshold_Metals : Confidence_Threshold_FX;
   int threshold = DynamicScoreThreshold(baseThreshold);
   bool buy = (buy_effective >= threshold && buy_effective >= sell_effective);
   bool sell = (sell_effective >= threshold && sell_effective > buy_effective);

   if(buy && PositionsDirectionCount(_Symbol, POSITION_TYPE_BUY) > 0) { g_last_lock_reason = "STACK"; LogDecisionCSV("SKIP", score_buy, GetSpreadInPips(_Symbol), atr_pips, ema_slope_pips); return; }
   if(sell && PositionsDirectionCount(_Symbol, POSITION_TYPE_SELL) > 0) { g_last_lock_reason = "STACK"; LogDecisionCSV("SKIP", score_sell, GetSpreadInPips(_Symbol), atr_pips, ema_slope_pips); return; }

   if(!(buy || sell)) { g_last_lock_reason = "SCORE"; LogDecisionCSV("SKIP", (buy_setup?score_buy:score_sell), GetSpreadInPips(_Symbol), atr_pips, ema_slope_pips); return; }

   // Selective caps
   if(IsMetals())
   {
      if(g_trades_today_metals >= 3) { g_last_lock_reason = "METALS_LIMIT"; LogDecisionCSV("SKIP", score_buy.total>score_sell.total?score_buy:score_sell, GetSpreadInPips(_Symbol), atr_pips, ema_slope_pips); return; }
   }
   else
   {
      if(g_trades_today_fx >= 2) { g_last_lock_reason = "FX_LIMIT"; LogDecisionCSV("SKIP", score_buy.total>score_sell.total?score_buy:score_sell, GetSpreadInPips(_Symbol), atr_pips, ema_slope_pips); return; }
   }
   if(g_trades_today >= Max_Trades_Per_Day) { g_last_lock_reason = "DAILY_LIMIT"; LogDecisionCSV("SKIP", score_buy.total>score_sell.total?score_buy:score_sell, GetSpreadInPips(_Symbol), atr_pips, ema_slope_pips); return; }
   if(g_last_loss_time > 0 && (TimeCurrent() - g_last_loss_time) < 1800) { g_last_lock_reason = "LOSS_COOLDOWN"; LogDecisionCSV("SKIP", score_buy.total>score_sell.total?score_buy:score_sell, GetSpreadInPips(_Symbol), atr_pips, ema_slope_pips); return; }

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
   risk_pct *= RiskThrottleMultiplier();

   double entry = buy ? ask : bid;
   double lot = CalculateLotByRisk(entry, sl, risk_pct);
   if(lot <= 0) { g_last_lock_reason = "LOT_ZERO"; return; }

   trade.SetExpertMagicNumber(g_magic);
   trade.SetDeviationInPoints(10);
   bool ok = false;
   if(buy) ok = trade.Buy(lot, _Symbol, ask, sl, tp, "MadRabbit");
   if(sell) ok = trade.Sell(lot, _Symbol, bid, sl, tp, "MadRabbit");

   if(ok)
   {
      g_trades_today++;
      if(IsMetals()) g_trades_today_metals++; else g_trades_today_fx++;
      LogTradeCSV(buy ? "BUY" : "SELL", lot, entry, sl, tp, buy ? score_buy : score_sell);
      LogDecisionCSV(buy ? "BUY" : "SELL", buy ? score_buy : score_sell, GetSpreadInPips(_Symbol), atr_pips, ema_slope_pips);
      TelegramSend(StringFormat("Mad Rabbit %s %s | Score %d | SL %.5f TP %.5f", _Symbol, buy ? "BUY" : "SELL", g_last_score, sl, tp));
   }
   else
   {
      g_last_lock_reason = "ORDER_FAIL";
      LogDecisionCSV("SKIP", buy ? score_buy : score_sell, GetSpreadInPips(_Symbol), atr_pips, ema_slope_pips);
   }
}

void UpdateDashboard()
{
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   double pnl_pct = (equity - g_day_start_equity) / g_day_start_equity * 100.0;
   double dd_pct = (g_peak_equity > 0) ? (g_peak_equity - equity) / g_peak_equity * 100.0 : 0.0;

   string risk_mode = "Normal";
   if(DailyLimitsHit()) risk_mode = "Locked";
   else if(IsAsianSession() && Reduce_Asian_Risk) risk_mode = "Reduced";

   Comment(
      "Mad Rabbit | ", _Symbol, "\n",
      "Daily PnL: ", DoubleToString(pnl_pct, 2), "%\n",
      "Drawdown: ", DoubleToString(dd_pct, 2), "%\n",
      "Active Trades: ", PositionsTotal(), "\n",
      "Trades Today: ", g_trades_today, "\n",
      "Session: ", (IsInSession() ? "ON" : "OFF"), "\n",
      "Risk Mode: ", risk_mode, "\n",
      "Regime: ", g_last_regime, "\n",
      "Adaptive ATR: ", DoubleToString(g_dynamic_atr_min, 1), "-", DoubleToString(g_dynamic_atr_max, 1), " | SpreadMax: ", DoubleToString(g_dynamic_spread_max, 1), "\n",
      "Last Score: ", g_last_score, "\n",
      "AI: ", (Enable_AI_Signals ? g_last_ai_status : "OFF"), " | Sig: ", g_last_ai_signal, " (", DoubleToString(g_last_ai_confidence, 1), ")\n",
      "Lock: ", g_last_lock_reason
   );
}

// ---- MT5 Events ----
int OnInit()
{
   rsi_handle = iRSI(_Symbol, Analysis_Timeframe, RSI_Period, PRICE_CLOSE);
   macd_handle = iMACD(_Symbol, Analysis_Timeframe, MACD_Fast, MACD_Slow, MACD_Signal, PRICE_CLOSE);
   atr_handle = iATR(_Symbol, Analysis_Timeframe, ATR_Period);
   ema_handle = iMA(_Symbol, Analysis_Timeframe, EMA_Slope_Period, 0, MODE_EMA, PRICE_CLOSE);

   if(rsi_handle == INVALID_HANDLE || macd_handle == INVALID_HANDLE || atr_handle == INVALID_HANDLE || ema_handle == INVALID_HANDLE)
      return(INIT_FAILED);

   g_day_start_equity = AccountInfoDouble(ACCOUNT_EQUITY);
   g_peak_equity = g_day_start_equity;

   if(Telegram_Test_OnInit && Telegram_Enable)
      TelegramSend("Mad Rabbit EA started on " + _Symbol);

   RefreshAdaptiveLimits();
   EventSetTimer(Scan_Interval_Seconds);
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   EventKillTimer();
   if(rsi_handle != INVALID_HANDLE) IndicatorRelease(rsi_handle);
   if(macd_handle != INVALID_HANDLE) IndicatorRelease(macd_handle);
   if(atr_handle != INVALID_HANDLE) IndicatorRelease(atr_handle);
   if(ema_handle != INVALID_HANDLE) IndicatorRelease(ema_handle);
}

void OnTimer()
{
   RefreshAdaptiveLimits();
   RefreshAIAdvisoryCache();
   ManageOpenPositions();
   if(Enable_AI_Signals)
   {
      if(AI_Use_Only_Mode) EvaluateAI();
      else Evaluate();
   }
   else
   {
      Evaluate();
   }
   UpdateDashboard();
}

void OnTick()
{
   // no-op: logic runs on timer
}

void OnTradeTransaction(const MqlTradeTransaction &trans, const MqlTradeRequest &req, const MqlTradeResult &res)
{
   if(trans.type == TRADE_TRANSACTION_DEAL_ADD && trans.deal > 0)
   {
      long entry = (long)HistoryDealGetInteger(trans.deal, DEAL_ENTRY);
      if(entry == DEAL_ENTRY_OUT)
      {
         double profit = HistoryDealGetDouble(trans.deal, DEAL_PROFIT);
         if(profit < 0)
         {
            g_last_loss_time = TimeCurrent();
            g_session_losses++;
            if(g_session_losses >= 2)
            {
               // lock for 6 hours (safe deterministic future time)
               g_session_lock_until = TimeCurrent() + 6 * 3600;
            }
         }
      }
   }
}
