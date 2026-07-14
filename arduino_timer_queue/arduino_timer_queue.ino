const int MAX_TASKS = 50; // Maximum number of simultaneous cashews being tracked

struct Task {
  int command;
  unsigned long executeAt;
  bool active;
};

Task taskQueue[MAX_TASKS];

// DEFINE YOUR PINS HERE
const int VALVE_ZONE1 = 2;
const int VALVE_ZONE2 = 3;
const int VALVE_ZONE3 = 4;
const int VALVE_ZONE4 = 5;
const int VALVE_ZONE5 = 6;
const int LED_PIN = 13; // Built-in LED for visual confirmation

void setup() {
  Serial.begin(115200);
  
  // INITIALIZE PINS HERE
  pinMode(VALVE_ZONE1, OUTPUT);
  pinMode(VALVE_ZONE2, OUTPUT);
  pinMode(VALVE_ZONE3, OUTPUT);
  pinMode(VALVE_ZONE4, OUTPUT);
  pinMode(VALVE_ZONE5, OUTPUT);
  pinMode(LED_PIN, OUTPUT);
}

void loop() {
  // 1. READ SERIAL COMMAND FROM PYTHON
  // Expected format: "16|19170|" (Command|DelayMS|)
  if (Serial.available() > 0) {
    String input = Serial.readStringUntil('\n'); 
    
    int firstPipe = input.indexOf('|');
    int secondPipe = input.indexOf('|', firstPipe + 1);
    
    if (firstPipe > 0 && secondPipe > firstPipe) {
      int cmd = input.substring(0, firstPipe).toInt();
      unsigned long delayMs = input.substring(firstPipe + 1, secondPipe).toInt();
      
      // Add this new command to the hardware timer queue
      addTask(cmd, delayMs);
    }
  }

  // 2. CHECK HARDWARE TIMERS CONTINUOUSLY
  unsigned long currentMillis = millis();
  for (int i = 0; i < MAX_TASKS; i++) {
    if (taskQueue[i].active && currentMillis >= taskQueue[i].executeAt) {
      
      executeCommand(taskQueue[i].command); // Fire the valve
      taskQueue[i].active = false;          // Remove from queue
      
    }
  }
}

// Function to add a task to the queue
void addTask(int cmd, unsigned long delayMs) {
  unsigned long executeTime = millis() + delayMs;
  for (int i = 0; i < MAX_TASKS; i++) {
    if (!taskQueue[i].active) {
      taskQueue[i].command = cmd;
      taskQueue[i].executeAt = executeTime;
      taskQueue[i].active = true;
      return;
    }
  }
}

// Function to actually fire the valve
void executeCommand(int cmd) {
  // Turn on built-in LED to show a valve is firing
  digitalWrite(LED_PIN, HIGH);
  
  if (cmd == 11) { // Zone 1
    digitalWrite(VALVE_ZONE1, HIGH);
    delay(20); // Keep valve open for 20ms
    digitalWrite(VALVE_ZONE1, LOW);
  }
  else if (cmd == 16) { // Zone 2
    digitalWrite(VALVE_ZONE2, HIGH);
    delay(20); 
    digitalWrite(VALVE_ZONE2, LOW);
  }
  else if (cmd == 12) { // Zone 3
    digitalWrite(VALVE_ZONE3, HIGH);
    delay(20); 
    digitalWrite(VALVE_ZONE3, LOW);
  }
  else if (cmd == 13) { // Zone 4
    digitalWrite(VALVE_ZONE4, HIGH);
    delay(20); 
    digitalWrite(VALVE_ZONE4, LOW);
  }
  else if (cmd == 14) { // Zone 5
    digitalWrite(VALVE_ZONE5, HIGH);
    delay(20); 
    digitalWrite(VALVE_ZONE5, LOW);
  }
  
  // Turn off built-in LED
  digitalWrite(LED_PIN, LOW);
}
