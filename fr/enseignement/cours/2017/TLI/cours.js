function cirque() {
  var id = document.getElementById("introduction");
  var context = id.getContext("2d");
  context.strokeStyle =  "#00b33c";
  context.lineWidth = 10;
  context.beginPath();
  context.arc(150, 150, 100, 0, 2 * Math.PI);
  context.stroke();
}

function rectangle() {
  var id = document.getElementById("introduction");
  var context = id.getContext("2d");
  context.strokeStyle =  "#00b33c";
  context.lineWidth = 10;
  context.beginPath();
  context.rect(10, 10, 280, 280);
  context.stroke();
}

function moncanvastexte() {
  var id = document.getElementById("moncanvas");
  var context = id.getContext("2d");
  context.strokeStyle =  "#00b33c";
  context.lineWidth = 10;
  context.beginPath();
  context.rect(10, 10, 280, 380);
  context.stroke();
  context.font = "20px Arial";
  context.fillText("(0, 0)", 15, 40);
  context.fillText("(300, 400)", 140, 370);
  context.fillStyle =  "red";
  context.lineWidth = 10;
  context.beginPath();
  context.arc(10, 10, 10, 0, 2 * Math.PI);
  context.arc(290, 390, 10, 0, 2 * Math.PI);
  context.fill();
}

function ligne() {
  var id = document.getElementById("ligne");
  var context = id.getContext("2d");
  context.beginPath();
  context.strokeStyle =  "#00b33c";
  context.lineWidth = 10;
  context.moveTo(0,0);
  context.lineTo(300,400);
  context.stroke();
  context.fillStyle =  "red";
  context.lineWidth = 10;
  context.beginPath();
  context.arc(10, 10, 10, 0, 2 * Math.PI);
  context.arc(290, 390, 10, 0, 2 * Math.PI);
  context.fill();
  context.strokeStyle =  "black";
  context.fillStyle =  "black";
  context.font = "20px Arial";
  context.fillText("(0, 0)", 45, 40);
  context.fillText("(300, 400)", 130, 370);
}

function ligne2() {
  var id = document.getElementById("ligne2");
  var context = id.getContext("2d");
  context.strokeStyle =  "#00b33c";
  context.lineWidth = 10;
  context.moveTo(0,400);
  context.lineTo(300,0);
  context.stroke();
  context.fillStyle =  "red";
  context.lineWidth = 10;
  context.beginPath();
  context.arc(10, 390, 10, 0, 2 * Math.PI);
  context.arc(290, 10, 10, 0, 2 * Math.PI);
  context.fill();
  context.strokeStyle =  "black";
  context.fillStyle =  "black";
  context.font = "20px Arial";
  context.fillText("(0, 400)", 45, 375);
  context.fillText("(300, 0)", 140, 25);
}

function lignes1() {
  var id = document.getElementById("lignes1");
  var context = id.getContext("2d");
  context.strokeStyle =  "#00b33c";
  context.lineWidth = 10;
  context.beginPath();
  context.moveTo(0,0);
  context.lineTo(300,400);
  context.stroke();

  context.strokeStyle =  "red";
  context.moveTo(0,400);
  context.lineTo(300,0);
  context.stroke();
}

function lignes2() {
  var id = document.getElementById("lignes2");
  var context = id.getContext("2d");
  context.strokeStyle =  "#00b33c";
  context.lineWidth = 10;

  context.beginPath();
  context.moveTo(0,0);
  context.lineTo(300,400);
  context.stroke();

  context.beginPath();
  context.strokeStyle =  "red";
  context.moveTo(0,400);
  context.lineTo(300,0);
  context.stroke();
}

function arc1() {
  var id = document.getElementById("arc1");
  var context = id.getContext("2d");
  context.strokeStyle =  "#00b33c";
  context.lineWidth = 10;
  context.beginPath();
  context.arc(200, 150, 80, Math.PI, 1.5 * Math.PI);
  context.stroke();
  context.fillStyle =  "red";
  context.lineWidth = 10;
  context.beginPath();
  context.arc(200, 150, 10, 0, 2 * Math.PI);
  context.fill();
  context.strokeStyle =  "black";
  context.fillStyle =  "black";
  context.font = "20px Arial";
  context.fillText("(200, 150)", 100, 220);
}

function arc2() {
  var id = document.getElementById("arc2");
  var context = id.getContext("2d");
  context.strokeStyle =  "#00b33c";
  context.lineWidth = 10;
  context.beginPath();
  context.arc(200, 150, 80, Math.PI, 1.5 * Math.PI, true);
  context.stroke();
  context.fillStyle =  "red";
  context.lineWidth = 10;
  context.beginPath();
  context.arc(200, 150, 10, 0, 2 * Math.PI);
  context.fill();
  context.strokeStyle =  "black";
  context.fillStyle =  "black";
  context.font = "20px Arial";
  context.fillText("(200, 150)", 100, 120);
}

function arc3(nom, fill) {
  var id = document.getElementById(nom);
  var context = id.getContext("2d");
  context.strokeStyle =  "#00b33c";
  context.lineWidth = 10;
  context.beginPath();
  context.moveTo(0,70);
  context.lineTo(140,70);
  context.arcTo(200, 70, 200, 270, 50);
  context.lineTo(200,270);
  if(fill) {
    context.fillStyle =  "#00b33c";
    context.fill();
  }
  else {
    context.stroke();
  }
  context.fillStyle =  "red";
  context.lineWidth = 10;
  context.beginPath();
  context.arc(200, 70, 10, 0, 2 * Math.PI);
  context.fill();
  context.fillStyle =  "red";
  context.lineWidth = 10;
  context.beginPath();
  context.arc(200, 270, 10, 0, 2 * Math.PI);
  context.fill();
  context.fillStyle =  "red";
  context.lineWidth = 10;
  context.beginPath();
  context.arc(140, 70, 10, 0, 2 * Math.PI);
  context.fill();
  context.strokeStyle =  "black";
  context.fillStyle =  "black";
  context.font = "20px Arial";
  context.fillText("(140, 70)", 100, 100);
  context.fillText("(200, 70)", 210, 70);
  context.fillText("(200, 270)", 210, 270);
}

cirque();
rectangle();
moncanvastexte();

ligne();
ligne2();

lignes1();
lignes2();

arc1();
arc2();
arc3("arc3", false);
arc3("arc4", true);
