var vide = new Array(3);
for (i = 0; i< 3; i++) {
  vide[i] = new Array(3);
  for (j = 0; j< 3; j++) {
    vide[i][j] = 0; //vide
  }
}

turnX = false;
tic_tac_toe();

document.getElementById("tic_tac_toe").onmousedown  = function(event) {
  event = event || window.event;
  event.preventDefault();
  ajouter(this, event);
}

function lignes(x,y) {
  var id = document.getElementById("tic_tac_toe");
  var context = id.getContext("2d");
  context.strokeStyle =  "#00b33c";
  context.lineWidth = 10;
  context.moveTo(x+20,y+20);
  context.lineTo(x+180,y+180);
  context.moveTo(x+180,y+20);
  context.lineTo(x+20,y+180);
  context.stroke();
}

function cirque(x, y) {
  var id = document.getElementById("tic_tac_toe");
  var context = id.getContext("2d");
  context.strokeStyle =  "#00b33c";
  context.lineWidth = 10;
  context.beginPath();
  context.arc(x, y, 80, 0, 2 * Math.PI);
  context.stroke();
}

function tic_tac_toe() {
  var id = document.getElementById("tic_tac_toe");
  var context = id.getContext("2d");
  context.strokeStyle =  "#ffb33c";
  context.lineWidth = 10;
  context.moveTo(0,200);
  context.lineTo(600,200);
  context.moveTo(0,400);
  context.lineTo(600,400);

  context.moveTo(200,0);
  context.lineTo(200,600);
  context.moveTo(400,0);
  context.lineTo(400,600);
  context.stroke();
}

function verifier(indexX, indexY) {
    
}

function ajouter(canvas, event) {
  var posX = event.pageX - canvas.offsetLeft;
  var posY = event.pageY - canvas.offsetTop;
  var indexX = -1;
  var indexY = -1;

  if (posX < 200) {
    indexX = 0;
  } 
  else if (posX >= 200 && posX < 400) {
    indexX = 1;
  }
  else if (posX >= 400 && posX < 600) {
    indexX = 2;
  }
  if (posY < 200) {
    indexY = 0;
  } 
  else if (posY >= 200 && posY < 400) {
    indexY = 1;
  }
  else if (posY >= 400 && posY < 600) {
    indexY = 2;
  }

 console.log(posX + " " + posY); 
 console.log(indexX + " " + indexY); 
  if (indexX != -1 && indexY != -1) {
     if (vide[indexX][indexY] == 0) {
       if(turnX) {
          lignes(indexX * 200, indexY * 200);
          turnX = false;
          vide[indexX][indexY] = 1;
        }
        else {
          cirque(indexX * 200 + 100, indexY * 200 + 100);
          turnX = true;
          vide[indexX][indexY] = 2;
        }
        verifier(indexX, indexY);
     }
  }
}

