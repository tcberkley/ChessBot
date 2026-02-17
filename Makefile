CC = gcc
CFLAGS = -O3 -Wall -Wno-unused-variable -Wno-unused-function
LDFLAGS = -lm

TARGET = v13_engine
SRC = v13_engine.c

all: $(TARGET)

$(TARGET): $(SRC)
	$(CC) $(CFLAGS) -o $(TARGET) $(SRC) $(LDFLAGS)

clean:
	rm -f $(TARGET)

.PHONY: all clean
