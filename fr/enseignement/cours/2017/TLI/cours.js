function moncanvas1() {
  var id = document.getElementById("moncanvas1");
  var context = id.getContext("2d");
  id.style.backgroundColor="green";
}

function cercle(nom) {
  var id = document.getElementById(nom);
  var context = id.getContext("2d");
  context.strokeStyle =  "#00b33c";
  context.lineWidth = 10;
  context.beginPath();
  context.arc(150, 150, 100, 0, 2 * Math.PI);
  context.stroke();
}

function rectangle(nom, fill) {
  var id = document.getElementById(nom);
  var context = id.getContext("2d");
  context.strokeStyle =  "#00b33c";
  context.lineWidth = 10;
  if(fill) {
    context.fillStyle =  "#00b33c";
    context.fillRect(10, 10, 280, 280);
  }
  else {
    context.rect(10, 10, 280, 280);
    context.stroke();
  }
}

function moncanvastexte() {
  var id = document.getElementById("moncanvas");
  var context = id.getContext("2d");
  context.strokeStyle =  "#00b33c";
  context.lineWidth = 10;
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

function courbequadratique(nom, bezier) {
  var id = document.getElementById(nom);
  var context = id.getContext("2d");
  context.strokeStyle =  "#00b33c";
  context.lineWidth = 10;
  context.beginPath();
  context.moveTo(0,70);
  context.lineTo(120,70);
  if(bezier) {
    context.bezierCurveTo(280, 120, 240, 220, 150, 270);
  }
  else {
    context.quadraticCurveTo(280, 120, 200, 270);
  }
  context.stroke();
  if(bezier) {
    context.fillStyle =  "red";
    context.lineWidth = 10;
    context.beginPath();
    context.arc(150, 270, 10, 0, 2 * Math.PI);
    context.fill();

    context.fillStyle =  "red";
    context.lineWidth = 10;
    context.beginPath();
    context.arc(240, 220, 10, 0, 2 * Math.PI);
    context.fill();
  }
  else {
    context.fillStyle =  "red";
    context.lineWidth = 10;
    context.beginPath();
    context.arc(200, 270, 10, 0, 2 * Math.PI);
    context.fill();
  }
  context.fillStyle =  "red";
  context.lineWidth = 10;
  context.beginPath();
  context.arc(280, 120, 10, 0, 2 * Math.PI);
  context.fill();
  context.fillStyle =  "red";
  context.lineWidth = 10;
  context.beginPath();
  context.arc(120, 70, 10, 0, 2 * Math.PI);
  context.fill();
  context.strokeStyle =  "black";
  context.fillStyle =  "black";
  context.font = "20px Arial";
  context.fillText("(120, 70)", 100, 100);
  context.fillText("(280, 120)", 180, 150);
  if(bezier) {
    context.fillText("(240, 220)", 210, 250);
    context.fillText("(150, 270)", 50, 270);
  }
  else {
    context.fillText("(200, 270)", 210, 270);
  }
}

function triangle(nom, fill) {
  var id = document.getElementById(nom);
  var context = id.getContext("2d");
  context.strokeStyle =  "#00b33c";
  context.lineWidth = 10;
  context.beginPath
  context.moveTo(10,10);
  context.lineTo(150,380);
  context.lineTo(280,10);
  context.closePath();
  if(fill) {
    context.fillStyle =  "#00b33c";
    context.fill()
  }
  else {
    context.stroke();
  }
}

function hexagone(nom, fill) {
  var id = document.getElementById(nom);
  var context = id.getContext("2d");
  context.strokeStyle =  "#00b33c";
  context.lineWidth = 10;
  context.beginPath();
  context.moveTo(10,200);
  context.lineTo(80,10);
  context.lineTo(200,10);
  context.lineTo(270,200);
  context.lineTo(200,380);
  context.lineTo(80,380);
  context.closePath();
  if(fill) {
    context.fillStyle =  "#00b33c";
    context.fill()
  }
  else {
    context.stroke();
  }
}

function effacer(nom){
  var id = document.getElementById(nom);
  var context = id.getContext("2d");
  hexagone(nom, true);
  context.clearRect(90, 140, 100, 100);
}

function bonjour(nom, fill){
  var id = document.getElementById(nom);
  var context = id.getContext("2d");

  context.font = "40px Arial";
  if (fill) {
    context.fillText("Bonjour!", 100, 100);
  }
  else {
    context.strokeText("Bonjour!", 100, 100);
  }
}

function pointeur(nom){
  var id = document.getElementById(nom);
  var context = id.getContext("2d");
  bonjour(nom);

  context.fillStyle =  "red";
  context.lineWidth = 10;
  context.beginPath();
  context.arc(100, 100, 10, 0, 2 * Math.PI);
  context.fill();
}

function alignement(nom){
  var id = document.getElementById(nom);
  var context = id.getContext("2d");

  context.strokeStyle = "red";
  context.lineWidth = 10;
  context.beginPath();
  context.moveTo(250,0);
  context.lineTo(250,400);
  context.closePath();
  context.stroke();

  context.font = "30px Arial";
  context.textAlign = "start";
  context.fillText("début", 250, 20);

  context.textAlign = "end";
  context.fillText("fin1 fin2 fin3 fin4 fin5 fin6", 250, 100);

  context.textAlign = "left";
  context.fillText("gauche1 gauche2 gauche3 gauche4", 250, 180);

  context.textAlign = "right";
  context.fillText("droite1 droite2 droite3 droite4", 250, 260);

  context.textAlign = "center";
  context.fillText("centre", 250, 340);
}

function base(nom){
  var id = document.getElementById(nom);
  var context = id.getContext("2d");

  context.strokeStyle = "red";
  context.lineWidth = 2;
  context.beginPath();
  context.moveTo(0,200);
  context.lineTo(500,200);
  context.closePath();
  context.stroke();

  context.font = "25px Arial";
  context.textBaseline = "top";
  context.fillText("haut", 0, 200);

  context.textBaseline = "middle";
  context.fillText("moyen", 150, 200);

  context.textBaseline = "alphabetic";
  context.fillText("alphabetique", 250, 200);

  context.textBaseline = "bottom";
  context.fillText("en bas", 420, 200);
}

function image() {
  var id = document.getElementById("image");
  var context = id.getContext("2d");
  var img = new Image();
  img.src = "800px-Detailaufnahme_Weihnachtsstern_-_groß.bmp";
  img.onload = function() {
    context.drawImage(img, 0, 0);
  }
}

function imagezone() {
  var id = document.getElementById("imagezone");
  var context = id.getContext("2d");
  var img = new Image();
  img.src = "800px-Detailaufnahme_Weihnachtsstern_-_groß.bmp";
  img.onload = function() {
    context.drawImage(img, 0, 0, 500, 400);
  }
}

function imagezone2() {
  var id = document.getElementById("imagezone2");
  var context = id.getContext("2d");
  var img = new Image();
  img.src = "800px-Detailaufnahme_Weihnachtsstern_-_groß.bmp";
  img.onload = function() {
    context.drawImage(img, 0, 0, 250, 200);
    context.drawImage(img, 250, 0, 250, 200);
    context.drawImage(img, 0, 200, 250, 200);
    context.drawImage(img, 250, 200, 250, 200);
  }
}

function imagedecoupage() {
  var id = document.getElementById("imagedecoupage");
  var context = id.getContext("2d");
  var img = new Image();
  img.src = "800px-Detailaufnahme_Weihnachtsstern_-_groß.bmp";
  img.onload = function() {
    context.drawImage(img, 100, 100, 500, 400, 250, 250, 150, 150);
  }
}

function imageRotate() {
  var id = document.getElementById("imageRotate");
  var context = id.getContext("2d");
  var img = new Image();
  img.src = "800px-Detailaufnahme_Weihnachtsstern_-_groß.bmp";
  img.onload = function() {
    context.rotate(10*Math.PI/180);
    context.drawImage(img, 200, 0, 200, 200);
  }
}

function imageScale() {
  var id = document.getElementById("imageScale");
  var context = id.getContext("2d");
  var img = new Image();
  img.src = "800px-Detailaufnahme_Weihnachtsstern_-_groß.bmp";
  img.onload = function() {
    context.scale(0.5, 0.5);
    context.drawImage(img, 200, 0, 200, 200);
  }
}

function imageTranslate() {
  var id = document.getElementById("imageTranslate");
  var context = id.getContext("2d");
  var img = new Image();
  img.src = "800px-Detailaufnahme_Weihnachtsstern_-_groß.bmp";
  img.onload = function() {
    context.drawImage(img, 0, 0, 200, 200);
    context.translate(200, 200);
    context.drawImage(img, 0, 0, 400, 400);
  }
}

function imageTransform() {
  var id = document.getElementById("imageTransform");
  var context = id.getContext("2d");
  var img = new Image();
  img.src = "800px-Detailaufnahme_Weihnachtsstern_-_groß.bmp";
  img.onload = function() {
    context.drawImage(img, 0, 0, 200, 200);
    context.transform(0.5, 0.5, -0.5, 0.5, 300,10);
    context.drawImage(img, 0, 0, 400, 400);
  }
}

image();
imageRotate();
imageScale();
imageTranslate();
imageTransform();

cercle("introduction");
rectangle("introduction", false);
moncanvastexte();

ligne();
ligne2();

lignes1();
lignes2();

arc1();
arc2();
arc3("arc3", false);
arc3("arc4", true);
courbequadratique("courbe1", false);
courbequadratique("courbe2", true);

cercle("cercle");
rectangle("rectangle1", false);
rectangle("rectangle2", true);
triangle("triangle1", false);
triangle("triangle2", true);

hexagone("hexagone1", false);
hexagone("hexagone2", true);

effacer("clearrect");

bonjour("texte1", false);
bonjour("texte2", true);

pointeur("pointeur");
alignement("alignement");
base("alignementbase");

image();
imagezone();
imagezone2();
imagedecoupage();

moncanvas1();
