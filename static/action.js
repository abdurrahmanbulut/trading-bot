document.addEventListener('DOMContentLoaded', function() {
  const startStopButton = document.getElementById('start-stop');
  const coinNameSelect = document.getElementById('coin-name');
  const dataRangeSelect = document.getElementById('data-range');
  const amountPercentage = document.getElementById('amount-percentage');
  const balanceSpan = document.getElementById('balance');

  // Event listener for the Start/Stop button
  startStopButton.addEventListener('click', function() {
    console.log("click");

    
    
    // This will toggle the button text as a placeholder
    const isRunning = startStopButton.textContent.includes('Stop');
    startStopButton.textContent = isRunning ? 'Start' : 'Stop';
    
    // Send AJAX request to Flask backend
    fetch('/start-stop', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        running: !isRunning,
        coin_name: coinNameSelect.value,
        data_range: dataRangeSelect.value,
        amount_percentage: amountPercentage.value,
        balance: parseInt(balanceSpan.textContent, 10)
      }) // Send the current state and additional info
    })
    .then(response => response.json())
    .then(data => {
      console.log("data.new_balance");
      console.log(data.new_balance);
      // Update the balance if it's changed by the Python method
      if (data.new_balance !== undefined) {
        console.log(data.new_balance);
        document.getElementById('balance').textContent = data.new_balance;
      }
      if (data.predictions !== undefined) {
        updatePredictions(data.predictions);
      }
    })
    .catch(error => {
      console.error('Error:', error);
    });
  });

  fetchChartData(coinNameSelect.value, dataRangeSelect.value);
  setInterval(fetchTradeHistory, 10000);
});




function fetchTradeHistory() {
  fetch('/get-trade-history', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
  })
    .then(response => response.json())
    .then(tradeHistory => {
      console.log("fetc trade");
      console.log(tradeHistory);
      updateTradeHistory(tradeHistory);
    })
    .catch(error => {
      console.error('Error:', error);
    });
}


function updateTradeHistory(tradeHistory) {
  const tradeHistoryDiv = document.getElementById('trade-history');
  const list = document.createElement('ul');

  tradeHistory.forEach(item => {
    const listItem = document.createElement('li');
    listItem.textContent = `${item.time} - ${item.action} - ${item.amount}`;
    list.appendChild(listItem);
  });

  tradeHistoryDiv.innerHTML = '';
  tradeHistoryDiv.appendChild(list);
}



function fetchChartData(coinName, dataRange) {
  fetch('/get-chart-data', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      coin_name: coinName,
      data_range: dataRange
    })
  })
    .then(response => response.json())
    .then(data => {
      updatePredictions(data.prediction_data);
    })
    .catch(error => {
      console.error('Error:', error);
    });
}

// Define a variable outside the event listener to keep track of the chart instance
let priceChart;
function updatePredictions(predictions) {
  const ctx = document.getElementById('priceChart').getContext('2d');
  
  // Split the predictions array
  const initialData = predictions.slice(0, -10); // All but the last 10
  const last10Data = predictions.slice(-10); // Just the last 10

  // Create labels for the x-axis
  const labels = predictions.map((_, index) => `+${index}h`);

  // Destroy the existing chart instance if it exists
  if (priceChart) {
    priceChart.destroy();
  }

  // Create a new chart instance
  priceChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: labels,
      datasets: [
        {
          label: 'Initial Predicted Price',
          data: initialData,
          fill: false,
          borderColor: 'rgb(75, 192, 192)',
          tension: 0.1
        },
        {
          label: 'Last 10 Predicted Prices',
          data: [...Array(initialData.length).fill(null), ...last10Data], // Pad the beginning with nulls
          fill: false,
          borderColor: 'rgb(255, 99, 132)',
          tension: 0.1
        }
      ]
    },
    options: {
      scales: {
        x: {
          title: {
            display: true,
            text: 'Time after current hour'
          }
        },
        y: {
          title: {
            display: true,
            text: 'Price'
          }
        }
      }
    }
  });
}

