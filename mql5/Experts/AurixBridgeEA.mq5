//+------------------------------------------------------------------+
//| AURIX Bridge EA                                                  |
//| Mac/Wine-safe bridge: MT5 EA <-> Python FastAPI                  |
//+------------------------------------------------------------------+
#property strict

#include <Trade/Trade.mqh>

input string TerminalId       = "AURIX-VPS-001";
input string BridgeBaseUrl    = "http://127.0.0.1:8765";
input string ApiKey           = "";
input string TradeSymbol      = "XAUUSDm";
input int    PollSeconds      = 2;
input bool   BrokerExecutionEnabled = false;
input double EmergencyMaxVolume     = 0.01;
input int    MagicNumber      = 880001;
input int    DeviationPoints  = 20;

CTrade trade;
string ProcessedCommandIds[100];
int ProcessedCommandCount = 0;

//+------------------------------------------------------------------+
int OnInit()
{
   trade.SetExpertMagicNumber(MagicNumber);
   trade.SetDeviationInPoints(DeviationPoints);
   EventSetTimer(PollSeconds);
   Print("AURIX Bridge EA started. TerminalId=", TerminalId, " Bridge=", BridgeBaseUrl);
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   EventKillTimer();
   Print("AURIX Bridge EA stopped. Reason=", reason);
}

//+------------------------------------------------------------------+
void OnTimer()
{
   SendSnapshot();
   PollCommand();
}

//+------------------------------------------------------------------+
void OnTick()
{
   // Tick handling stays light. Snapshot/command polling is timer-based.
}

//+------------------------------------------------------------------+
string JsonEscape(string s)
{
   StringReplace(s, "\\", "\\\\");
   StringReplace(s, "\"", "\\\"");
   StringReplace(s, "\r", "\\r");
   StringReplace(s, "\n", "\\n");
   return s;
}

//+------------------------------------------------------------------+
string Num(double v, int digits=8)
{
   return DoubleToString(v, digits);
}

//+------------------------------------------------------------------+
string AccountJson()
{
   string j = "{";
   j += "\"login\":" + IntegerToString((long)AccountInfoInteger(ACCOUNT_LOGIN)) + ",";
   j += "\"server\":\"" + JsonEscape(AccountInfoString(ACCOUNT_SERVER)) + "\",";
   j += "\"currency\":\"" + JsonEscape(AccountInfoString(ACCOUNT_CURRENCY)) + "\",";
   j += "\"company\":\"" + JsonEscape(AccountInfoString(ACCOUNT_COMPANY)) + "\",";
   j += "\"name\":\"" + JsonEscape(AccountInfoString(ACCOUNT_NAME)) + "\",";
   j += "\"account_login\":" + IntegerToString((long)AccountInfoInteger(ACCOUNT_LOGIN)) + ",";
   j += "\"account_server\":\"" + JsonEscape(AccountInfoString(ACCOUNT_SERVER)) + "\",";
   j += "\"account_currency\":\"" + JsonEscape(AccountInfoString(ACCOUNT_CURRENCY)) + "\",";
   j += "\"account_company\":\"" + JsonEscape(AccountInfoString(ACCOUNT_COMPANY)) + "\",";
   j += "\"account_name\":\"" + JsonEscape(AccountInfoString(ACCOUNT_NAME)) + "\",";
   j += "\"account_trade_mode\":" + IntegerToString((int)AccountInfoInteger(ACCOUNT_TRADE_MODE)) + ",";
   j += "\"is_demo\":" + (AccountInfoInteger(ACCOUNT_TRADE_MODE) == ACCOUNT_TRADE_MODE_DEMO ? "true" : "false") + ",";
   j += "\"balance\":" + Num(AccountInfoDouble(ACCOUNT_BALANCE), 2) + ",";
   j += "\"equity\":" + Num(AccountInfoDouble(ACCOUNT_EQUITY), 2) + ",";
   j += "\"profit\":" + Num(AccountInfoDouble(ACCOUNT_PROFIT), 2) + ",";
   j += "\"margin\":" + Num(AccountInfoDouble(ACCOUNT_MARGIN), 2) + ",";
   j += "\"margin_free\":" + Num(AccountInfoDouble(ACCOUNT_MARGIN_FREE), 2) + ",";
   j += "\"margin_level\":" + Num(AccountInfoDouble(ACCOUNT_MARGIN_LEVEL), 2) + ",";
   j += "\"leverage\":" + IntegerToString((long)AccountInfoInteger(ACCOUNT_LEVERAGE)) + ",";
   j += "\"trade_allowed\":" + (AccountInfoInteger(ACCOUNT_TRADE_ALLOWED) ? "true" : "false") + ",";
   j += "\"trade_expert\":" + (AccountInfoInteger(ACCOUNT_TRADE_EXPERT) ? "true" : "false");
   j += "}";
   return j;
}

//+------------------------------------------------------------------+
string TickJson(string symbol)
{
   MqlTick tick;
   bool ok = SymbolInfoTick(symbol, tick);
   double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
   double spread = 0;
   if(ok && point > 0)
      spread = (tick.ask - tick.bid) / point;

   string j = "{";
   j += "\"symbol\":\"" + JsonEscape(symbol) + "\",";
   j += "\"ok\":" + (ok ? "true" : "false") + ",";
   j += "\"time\":" + IntegerToString((long)tick.time) + ",";
   j += "\"bid\":" + Num(tick.bid) + ",";
   j += "\"ask\":" + Num(tick.ask) + ",";
   j += "\"last\":" + Num(tick.last) + ",";
   j += "\"volume\":" + Num((double)tick.volume) + ",";
   j += "\"spread_points\":" + Num(spread, 2);
   j += "}";
   return j;
}

//+------------------------------------------------------------------+
string CandlesJson(string symbol)
{
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   int copied = CopyRates(symbol, PERIOD_M1, 0, 20, rates);

   string j = "[";
   for(int i = copied - 1; i >= 0; i--)
   {
      j += "{";
      j += "\"time\":" + IntegerToString((long)rates[i].time) + ",";
      j += "\"open\":" + Num(rates[i].open) + ",";
      j += "\"high\":" + Num(rates[i].high) + ",";
      j += "\"low\":" + Num(rates[i].low) + ",";
      j += "\"close\":" + Num(rates[i].close) + ",";
      j += "\"tick_volume\":" + IntegerToString((long)rates[i].tick_volume) + ",";
      j += "\"spread\":" + IntegerToString(rates[i].spread) + ",";
      j += "\"real_volume\":" + IntegerToString((long)rates[i].real_volume);
      j += "}";
      if(i > 0) j += ",";
   }
   j += "]";
   return j;
}

//+------------------------------------------------------------------+
string PositionsJson()
{
   string j = "[";
   int total = PositionsTotal();
   int added = 0;

   for(int i = 0; i < total; i++)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;

      string symbol = PositionGetString(POSITION_SYMBOL);

      if(added > 0) j += ",";
      j += "{";
      j += "\"ticket\":" + IntegerToString((long)ticket) + ",";
      j += "\"symbol\":\"" + JsonEscape(symbol) + "\",";
      j += "\"type\":" + IntegerToString((int)PositionGetInteger(POSITION_TYPE)) + ",";
      j += "\"magic\":" + IntegerToString((long)PositionGetInteger(POSITION_MAGIC)) + ",";
      j += "\"volume\":" + Num(PositionGetDouble(POSITION_VOLUME), 2) + ",";
      j += "\"price_open\":" + Num(PositionGetDouble(POSITION_PRICE_OPEN)) + ",";
      j += "\"sl\":" + Num(PositionGetDouble(POSITION_SL)) + ",";
      j += "\"tp\":" + Num(PositionGetDouble(POSITION_TP)) + ",";
      j += "\"price_current\":" + Num(PositionGetDouble(POSITION_PRICE_CURRENT)) + ",";
      j += "\"profit\":" + Num(PositionGetDouble(POSITION_PROFIT), 2) + ",";
      j += "\"swap\":" + Num(PositionGetDouble(POSITION_SWAP), 2) + ",";
      j += "\"comment\":\"" + JsonEscape(PositionGetString(POSITION_COMMENT)) + "\"";
      j += "}";
      added++;
   }

   j += "]";
   return j;
}

//+------------------------------------------------------------------+
string OrdersJson()
{
   string j = "[";
   int total = OrdersTotal();
   int added = 0;

   for(int i = 0; i < total; i++)
   {
      ulong ticket = OrderGetTicket(i);
      if(ticket == 0) continue;

      if(added > 0) j += ",";
      j += "{";
      j += "\"ticket\":" + IntegerToString((long)ticket) + ",";
      j += "\"symbol\":\"" + JsonEscape(OrderGetString(ORDER_SYMBOL)) + "\",";
      j += "\"type\":" + IntegerToString((int)OrderGetInteger(ORDER_TYPE)) + ",";
      j += "\"state\":" + IntegerToString((int)OrderGetInteger(ORDER_STATE)) + ",";
      j += "\"magic\":" + IntegerToString((long)OrderGetInteger(ORDER_MAGIC)) + ",";
      j += "\"volume_current\":" + Num(OrderGetDouble(ORDER_VOLUME_CURRENT), 2) + ",";
      j += "\"volume_initial\":" + Num(OrderGetDouble(ORDER_VOLUME_INITIAL), 2) + ",";
      j += "\"price_open\":" + Num(OrderGetDouble(ORDER_PRICE_OPEN)) + ",";
      j += "\"sl\":" + Num(OrderGetDouble(ORDER_SL)) + ",";
      j += "\"tp\":" + Num(OrderGetDouble(ORDER_TP)) + ",";
      j += "\"comment\":\"" + JsonEscape(OrderGetString(ORDER_COMMENT)) + "\"";
      j += "}";
      added++;
   }

   j += "]";
   return j;
}

//+------------------------------------------------------------------+
string DealsJson()
{
   datetime to = TimeCurrent();
   datetime from = to - 86400 * 3;
   HistorySelect(from, to);

   int total = HistoryDealsTotal();
   int start = MathMax(0, total - 20);

   string j = "[";
   int added = 0;

   for(int i = start; i < total; i++)
   {
      ulong ticket = HistoryDealGetTicket(i);
      if(ticket == 0) continue;

      if(added > 0) j += ",";
      j += "{";
      j += "\"ticket\":" + IntegerToString((long)ticket) + ",";
      j += "\"order\":" + IntegerToString((long)HistoryDealGetInteger(ticket, DEAL_ORDER)) + ",";
      j += "\"time\":" + IntegerToString((long)HistoryDealGetInteger(ticket, DEAL_TIME)) + ",";
      j += "\"symbol\":\"" + JsonEscape(HistoryDealGetString(ticket, DEAL_SYMBOL)) + "\",";
      j += "\"type\":" + IntegerToString((int)HistoryDealGetInteger(ticket, DEAL_TYPE)) + ",";
      j += "\"entry\":" + IntegerToString((int)HistoryDealGetInteger(ticket, DEAL_ENTRY)) + ",";
      j += "\"magic\":" + IntegerToString((long)HistoryDealGetInteger(ticket, DEAL_MAGIC)) + ",";
      j += "\"volume\":" + Num(HistoryDealGetDouble(ticket, DEAL_VOLUME), 2) + ",";
      j += "\"price\":" + Num(HistoryDealGetDouble(ticket, DEAL_PRICE)) + ",";
      j += "\"profit\":" + Num(HistoryDealGetDouble(ticket, DEAL_PROFIT), 2) + ",";
      j += "\"commission\":" + Num(HistoryDealGetDouble(ticket, DEAL_COMMISSION), 2) + ",";
      j += "\"swap\":" + Num(HistoryDealGetDouble(ticket, DEAL_SWAP), 2) + ",";
      j += "\"comment\":\"" + JsonEscape(HistoryDealGetString(ticket, DEAL_COMMENT)) + "\"";
      j += "}";
      added++;
   }

   j += "]";
   return j;
}

//+------------------------------------------------------------------+
bool HttpPostJson(string path, string payload, string &response)
{
   string url = BridgeBaseUrl + path;
   string headers = "Content-Type: application/json\r\n";
   if(ApiKey != "")
      headers += "X-AURIX-API-Key: " + ApiKey + "\r\n";
   char data[];
   char result[];
   string result_headers;

   StringToCharArray(payload, data, 0, WHOLE_ARRAY, CP_UTF8);
   ResetLastError();

   int code = WebRequest("POST", url, headers, 5000, data, result, result_headers);
   response = CharArrayToString(result, 0, -1, CP_UTF8);

   if(code == -1)
   {
      Print("AURIX WebRequest POST failed. Error=", GetLastError(), " URL=", url);
      return false;
   }

   if(code < 200 || code >= 300)
   {
      Print("AURIX HTTP POST non-2xx. Code=", code, " Body=", response);
      return false;
   }

   return true;
}

//+------------------------------------------------------------------+
bool HttpGetText(string path, string &response)
{
   string url = BridgeBaseUrl + path;
   string headers = "";
   if(ApiKey != "")
      headers = "X-AURIX-API-Key: " + ApiKey + "\r\n";
   char data[];
   char result[];
   string result_headers;

   ResetLastError();
   int code = WebRequest("GET", url, headers, 5000, data, result, result_headers);
   response = CharArrayToString(result, 0, -1, CP_UTF8);

   if(code == -1)
   {
      Print("AURIX WebRequest GET failed. Error=", GetLastError(), " URL=", url);
      return false;
   }

   if(code < 200 || code >= 300)
   {
      Print("AURIX HTTP GET non-2xx. Code=", code, " Body=", response);
      return false;
   }

   return true;
}

//+------------------------------------------------------------------+
void SendSnapshot()
{
   string symbol = TradeSymbol;
   if(!SymbolSelect(symbol, true))
   {
      Print("AURIX cannot select symbol: ", symbol);
      return;
   }

   string payload = "{";
   payload += "\"terminal_id\":\"" + JsonEscape(TerminalId) + "\",";
   payload += "\"account\":" + AccountJson() + ",";
   payload += "\"tick\":" + TickJson(symbol) + ",";
   payload += "\"candles\":" + CandlesJson(symbol) + ",";
   payload += "\"positions\":" + PositionsJson() + ",";
   payload += "\"orders\":" + OrdersJson() + ",";
   payload += "\"deals\":" + DealsJson() + ",";
   payload += "\"raw\":{";
   payload += "\"ea\":\"AurixBridgeEA\",";
   payload += "\"broker_execution_enabled\":" + (BrokerExecutionEnabled ? "true" : "false") + ",";
   payload += "\"emergency_max_volume\":" + Num(EmergencyMaxVolume, 2) + ",";
   payload += "\"magic\":" + IntegerToString(MagicNumber);
   payload += "}";
   payload += "}";

   string response;
   HttpPostJson("/mt5/snapshot", payload, response);
}

//+------------------------------------------------------------------+
int SplitPipe(string text, string &parts[])
{
   return StringSplit(text, '|', parts);
}

//+------------------------------------------------------------------+
bool ConfirmAllowed(string confirm)
{
   if(!BrokerExecutionEnabled)
      return false;

   if(confirm != "I_ACCEPT_LIVE_RISK")
      return false;

   return true;
}

//+------------------------------------------------------------------+
void SendExecutionResult(
   string command_id,
   string status,
   int retcode,
   string message,
   ulong order_ticket,
   ulong deal_ticket,
   string symbol,
   string direction,
   double volume,
   double price,
   double sl,
   double tp
)
{
   string payload = "{";
   payload += "\"terminal_id\":\"" + JsonEscape(TerminalId) + "\",";
   payload += "\"command_id\":\"" + JsonEscape(command_id) + "\",";
   payload += "\"status\":\"" + JsonEscape(status) + "\",";
   payload += "\"ok\":" + (status == "FILLED" ? "true" : "false") + ",";
   payload += "\"retcode\":" + IntegerToString(retcode) + ",";
   payload += "\"error_code\":" + IntegerToString(retcode) + ",";
   payload += "\"error_message\":\"" + JsonEscape(message) + "\",";
   payload += "\"order\":" + IntegerToString((long)order_ticket) + ",";
   payload += "\"ticket\":" + IntegerToString((long)order_ticket) + ",";
   payload += "\"deal\":" + IntegerToString((long)deal_ticket) + ",";
   payload += "\"symbol\":\"" + JsonEscape(symbol) + "\",";
   payload += "\"side\":\"" + JsonEscape(direction) + "\",";
   payload += "\"volume\":" + Num(volume, 2) + ",";
   payload += "\"price\":" + Num(price) + ",";
   payload += "\"sl\":" + Num(sl) + ",";
   payload += "\"tp\":" + Num(tp) + ",";
   payload += "\"timestamp\":\"" + TimeToString(TimeCurrent(), TIME_DATE|TIME_SECONDS) + "\",";
   payload += "\"account\": " + AccountJson() + ",";
   payload += "\"raw\":{}";
   payload += "}";

   string response;
   HttpPostJson("/mt5/execution-result", payload, response);
}

//+------------------------------------------------------------------+
string JsonStringValue(string text, string key)
{
   string pattern = "\"" + key + "\":\"";
   int start = StringFind(text, pattern);
   if(start < 0) return "";
   start += StringLen(pattern);
   int end = StringFind(text, "\"", start);
   if(end < 0) return "";
   return StringSubstr(text, start, end - start);
}

//+------------------------------------------------------------------+
double JsonNumberValue(string text, string key)
{
   string pattern = "\"" + key + "\":";
   int start = StringFind(text, pattern);
   if(start < 0) return 0;
   start += StringLen(pattern);
   int end = start;
   while(end < StringLen(text))
   {
      string ch = StringSubstr(text, end, 1);
      if(ch == "," || ch == "}" || ch == " ") break;
      end++;
   }
   return StringToDouble(StringSubstr(text, start, end - start));
}

//+------------------------------------------------------------------+
bool AlreadyProcessed(string command_id)
{
   for(int i = 0; i < ProcessedCommandCount; i++)
      if(ProcessedCommandIds[i] == command_id)
         return true;
   return false;
}

//+------------------------------------------------------------------+
void RememberProcessed(string command_id)
{
   if(command_id == "") return;
   int idx = ProcessedCommandCount % 100;
   ProcessedCommandIds[idx] = command_id;
   ProcessedCommandCount++;
}

//+------------------------------------------------------------------+
bool IsDemoAccount()
{
   return AccountInfoInteger(ACCOUNT_TRADE_MODE) == ACCOUNT_TRADE_MODE_DEMO;
}

//+------------------------------------------------------------------+
void ExecuteDemoBrokerMarketJson(string response)
{
   string command_id = JsonStringValue(response, "command_id");
   string mode = JsonStringValue(response, "mode");
   string action = JsonStringValue(response, "action");
   string symbol = JsonStringValue(response, "symbol");
   string side = JsonStringValue(response, "side");
   double volume = JsonNumberValue(response, "volume");
   double sl = JsonNumberValue(response, "stop_loss");
   double tp = JsonNumberValue(response, "take_profit");

   if(AlreadyProcessed(command_id))
   {
      SendExecutionResult(command_id, "DUPLICATE", -20, "Duplicate command_id already processed", 0, 0, symbol, side, volume, 0, sl, tp);
      return;
   }
   RememberProcessed(command_id);

   if(mode != "DEMO_BROKER" || action != "OPEN_MARKET")
   {
      SendExecutionResult(command_id, "BLOCKED_BY_EA", -21, "Command mode/action blocked by EA", 0, 0, symbol, side, volume, 0, sl, tp);
      return;
   }
   if(!BrokerExecutionEnabled)
   {
      SendExecutionResult(command_id, "BLOCKED_BY_EA", -22, "BrokerExecutionEnabled is false", 0, 0, symbol, side, volume, 0, sl, tp);
      return;
   }
   if(!IsDemoAccount())
   {
      SendExecutionResult(command_id, "BLOCKED_BY_EA", -23, "Account is not demo", 0, 0, symbol, side, volume, 0, sl, tp);
      return;
   }
   if(symbol != TradeSymbol || symbol != "XAUUSDm")
   {
      SendExecutionResult(command_id, "BLOCKED_BY_EA", -24, "Symbol blocked by EA", 0, 0, symbol, side, volume, 0, sl, tp);
      return;
   }
   if(volume <= 0 || volume > EmergencyMaxVolume || volume > 0.01)
   {
      SendExecutionResult(command_id, "BLOCKED_BY_EA", -25, "Volume blocked by EA", 0, 0, symbol, side, volume, 0, sl, tp);
      return;
   }
   if(sl <= 0 || tp <= 0)
   {
      SendExecutionResult(command_id, "BLOCKED_BY_EA", -26, "SL/TP required", 0, 0, symbol, side, volume, 0, sl, tp);
      return;
   }
   if(PositionsTotal() > 0)
   {
      SendExecutionResult(command_id, "BLOCKED_BY_EA", -27, "Existing broker position blocks new demo order", 0, 0, symbol, side, volume, 0, sl, tp);
      return;
   }

   bool ok = false;
   if(side == "BUY")
      ok = trade.Buy(volume, symbol, 0, sl, tp, "AURIX-DEMO");
   else if(side == "SELL")
      ok = trade.Sell(volume, symbol, 0, sl, tp, "AURIX-DEMO");
   else
   {
      SendExecutionResult(command_id, "REJECTED", -28, "Unknown side", 0, 0, symbol, side, volume, 0, sl, tp);
      return;
   }

   int retcode = (int)trade.ResultRetcode();
   string msg = trade.ResultRetcodeDescription();
   string status = ok ? "FILLED" : "ERROR";
   SendExecutionResult(command_id, status, retcode, msg, trade.ResultOrder(), trade.ResultDeal(), symbol, side, volume, trade.ResultPrice(), sl, tp);
}

//+------------------------------------------------------------------+
void ExecuteOpenMarket(string &parts[])
{
   // OPEN_MARKET|cmd_id|symbol|direction|volume|sl|tp|comment|confirm
   string cmd_id   = parts[1];
   string symbol   = parts[2];
   string dir      = parts[3];
   double volume   = StringToDouble(parts[4]);
   double sl       = StringToDouble(parts[5]);
   double tp       = StringToDouble(parts[6]);
   string comment  = parts[7];
   string confirm  = parts[8];

   if(!ConfirmAllowed(confirm))
   {
      SendExecutionResult(cmd_id, "BLOCKED_BY_EA", -1, "Live trading blocked by EA safety gate", 0, 0, symbol, dir, volume, 0, sl, tp);
      return;
   }

   if(volume <= 0 || volume > EmergencyMaxVolume)
   {
      SendExecutionResult(cmd_id, "BLOCKED_BY_EA", -2, "Volume blocked by EmergencyMaxVolume", 0, 0, symbol, dir, volume, 0, sl, tp);
      return;
   }

   if(!SymbolSelect(symbol, true))
   {
      SendExecutionResult(cmd_id, "ERROR", -3, "SymbolSelect failed", 0, 0, symbol, dir, volume, 0, sl, tp);
      return;
   }

   bool ok = false;
   if(dir == "BUY")
      ok = trade.Buy(volume, symbol, 0, sl, tp, comment);
   else if(dir == "SELL")
      ok = trade.Sell(volume, symbol, 0, sl, tp, comment);
   else
   {
      SendExecutionResult(cmd_id, "REJECTED", -4, "Unknown direction", 0, 0, symbol, dir, volume, 0, sl, tp);
      return;
   }

   int retcode = (int)trade.ResultRetcode();
   string msg = trade.ResultRetcodeDescription();
   ulong order_ticket = trade.ResultOrder();
   ulong deal_ticket = trade.ResultDeal();
   double price = trade.ResultPrice();

   SendExecutionResult(cmd_id, ok ? "FILLED" : "ERROR", retcode, msg, order_ticket, deal_ticket, symbol, dir, volume, price, sl, tp);
}

//+------------------------------------------------------------------+
void ExecuteClosePosition(string &parts[])
{
   // CLOSE_POSITION|cmd_id|ticket|volume|comment|confirm
   string cmd_id  = parts[1];
   ulong ticket   = (ulong)StringToInteger(parts[2]);
   double volume  = StringToDouble(parts[3]);
   string comment = parts[4];
   string confirm = parts[5];

   if(!ConfirmAllowed(confirm))
   {
      SendExecutionResult(cmd_id, "BLOCKED_BY_EA", -1, "Close blocked by EA safety gate", ticket, 0, "", "CLOSE", volume, 0, 0, 0);
      return;
   }

   bool selected = PositionSelectByTicket(ticket);
   if(!selected)
   {
      SendExecutionResult(cmd_id, "ERROR", -2, "Position ticket not found", ticket, 0, "", "CLOSE", volume, 0, 0, 0);
      return;
   }

   string symbol = PositionGetString(POSITION_SYMBOL);
   double pos_volume = PositionGetDouble(POSITION_VOLUME);

   bool ok;
   if(volume > 0 && volume < pos_volume)
      ok = trade.PositionClosePartial(ticket, volume, DeviationPoints);
   else
      ok = trade.PositionClose(ticket, DeviationPoints);

   int retcode = (int)trade.ResultRetcode();
   string msg = trade.ResultRetcodeDescription();
   ulong order_ticket = trade.ResultOrder();
   ulong deal_ticket = trade.ResultDeal();
   double price = trade.ResultPrice();

   SendExecutionResult(cmd_id, ok ? "FILLED" : "ERROR", retcode, msg, order_ticket, deal_ticket, symbol, "CLOSE", volume, price, 0, 0);
}

//+------------------------------------------------------------------+
void ExecuteKillSwitch(string &parts[])
{
   // KILL_SWITCH|cmd_id|comment|confirm
   string cmd_id = parts[1];
   string confirm = parts[3];

   if(!ConfirmAllowed(confirm))
   {
      SendExecutionResult(cmd_id, "BLOCKED_BY_EA", -1, "Kill switch blocked by EA safety gate", 0, 0, "", "KILL", 0, 0, 0, 0);
      return;
   }

   bool all_ok = true;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(!trade.PositionClose(ticket, DeviationPoints))
         all_ok = false;
   }

   SendExecutionResult(cmd_id, all_ok ? "FILLED" : "ERROR", (int)trade.ResultRetcode(), "Kill switch processed", trade.ResultOrder(), trade.ResultDeal(), "", "KILL", 0, trade.ResultPrice(), 0, 0);
}

//+------------------------------------------------------------------+
void PollCommand()
{
   string response;
   string path = "/mt5/command?terminal_id=" + TerminalId;

   if(!HttpGetText(path, response))
      return;

   StringTrimLeft(response);
   StringTrimRight(response);

   if(response == "" || response == "NOOP" || StringFind(response, "\"status\":\"NO_COMMAND\"") >= 0 || StringFind(response, "\"command\":null") >= 0)
      return;

   if(StringFind(response, "\"mode\":\"DEMO_BROKER\"") >= 0 || StringFind(response, "\"mode\": \"DEMO_BROKER\"") >= 0)
   {
      ExecuteDemoBrokerMarketJson(response);
      return;
   }

   string parts[];
   int n = SplitPipe(response, parts);
   if(n < 2)
   {
      Print("AURIX invalid command: ", response);
      return;
   }

   string cmd = parts[0];

   if(cmd == "OPEN_MARKET" && n >= 9)
      ExecuteOpenMarket(parts);
   else if(cmd == "CLOSE_POSITION" && n >= 6)
      ExecuteClosePosition(parts);
   else if(cmd == "KILL_SWITCH" && n >= 4)
      ExecuteKillSwitch(parts);
   else
      Print("AURIX unknown/invalid command: ", response);
}
//+------------------------------------------------------------------+
